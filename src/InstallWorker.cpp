#include "InstallWorker.h"
#include "Common.h"
#include <QProcess>
#include <QDebug>
#include <QStandardPaths>
#include <QApplication>
#include <cstdlib>
#include <unistd.h>
#include <pty.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <errno.h>
#include <poll.h>

InstallWorker::InstallWorker(const QString &disk, const QString &image, int rootfsSize, int espSize, int etcSize, int varSize, bool dualBoot, const QString &filesystemType, bool secureBootEnabled, const QString &locale, const QString &timezone, const QString &keyboard, const QString &fullname, const QString &username, const QString &password, const QString &rootPassword, QObject *parent)
: QThread(parent)
, m_disk(disk)
, m_image(image)
, m_rootfsSize(rootfsSize)
, m_espSize(espSize)
, m_etcSize(etcSize)
, m_varSize(varSize)
, m_dualBoot(dualBoot)
, m_filesystemType(filesystemType)
, m_secureBootEnabled(secureBootEnabled)
, m_locale(locale)
, m_timezone(timezone)
, m_keyboard(keyboard)
, m_fullname(fullname)
, m_username(username)
, m_password(password)
, m_rootPassword(rootPassword)
, m_inChroot(false)
, m_masterFd(-1)
, m_slaveFd(-1)
, m_childPid(-1)
, m_waitingForChrootResponse(false)
{
}

InstallWorker::~InstallWorker()
{
    cleanup();
}

void InstallWorker::cleanup()
{
    if (m_childPid > 0) {
        kill(m_childPid, SIGTERM);
        waitpid(m_childPid, nullptr, WNOHANG);
        m_childPid = -1;
    }

    if (m_masterFd >= 0) {
        close(m_masterFd);
        m_masterFd = -1;
    }
    if (m_slaveFd >= 0) {
        close(m_slaveFd);
        m_slaveFd = -1;
    }
}

bool InstallWorker::setupPty()
{
    struct winsize ws;
    ws.ws_row = 24;
    ws.ws_col = 80;
    ws.ws_xpixel = 0;
    ws.ws_ypixel = 0;
    if (openpty(&m_masterFd, &m_slaveFd, nullptr, nullptr, &ws) == -1) {
        emit finished(false, QString("Failed to create PTY: %1").arg(strerror(errno)));
        return false;
    }

    struct termios tios;
    if (tcgetattr(m_slaveFd, &tios) == 0) {
        tios.c_lflag |= ECHO | ECHOE | ECHOK | ECHOCTL | ECHOKE;
        tios.c_lflag |= ICANON;
        tios.c_lflag &= ~ECHONL;
        tios.c_iflag |= ICRNL;
        tios.c_oflag |= OPOST | ONLCR;
        tcsetattr(m_slaveFd, TCSANOW, &tios);
    }

    int flags = fcntl(m_masterFd, F_GETFL, 0);
    fcntl(m_masterFd, F_SETFL, flags | O_NONBLOCK);
    return true;
}

void InstallWorker::run()
{
    try {
        QStringList cmd;
        bool testMode = QStandardPaths::findExecutable("obsidianctl").isEmpty() || isTestMode();
        if (testMode) {
            cmd = QStringList() << "sh" << "-c" <<
            "echo 'Test running...'; sleep 1; "
            "echo 'Partitioning disk...'; sleep 1; "
            "echo 'Installing system image...' >&2; sleep 1; "
            "echo 'Configuring bootloader...'; sleep 1; "
            "printf 'Do you want to chroot into slot a to make changes before copying it to slot B? (y/N): ' >&2; read answer; echo \"User answered: $answer\"; "
            "sleep 2; "
            "echo 'Installation complete'; exit 0";
            emit progressUpdated("Starting installation...");
        } else {
            cmd = QStringList()
                << "sudo" << "-S"
                << "obsidianctl" << "install"
                << m_disk << m_image
                << "--rootfs-size" << QString("%1G").arg(m_rootfsSize)
                << "--esp-size"    << QString("%1M").arg(m_espSize)
                << "--etc-size"    << QString("%1G").arg(m_etcSize)
                << "--var-size"    << QString("%1G").arg(m_varSize);
            if (m_dualBoot) {
                cmd << "--dual-boot";
            }
            if (m_secureBootEnabled) {
                cmd << "--secure-boot";
            }
            if (m_filesystemType == "f2fs") {
                cmd << "--use-f2fs";
            }
            emit progressUpdated("Starting installation...");
        }

        if (!setupPty()) {
            return;
        }

        m_childPid = fork();
        if (m_childPid == -1) {
            emit finished(false, QString("Failed to fork process: %1").arg(strerror(errno)));
            cleanup();
            return;
        }

        if (m_childPid == 0) {
            close(m_masterFd);
            if (setsid() == -1) {
                _exit(1);
            }

            if (ioctl(m_slaveFd, TIOCSCTTY, 0) == -1) {
                _exit(1);
            }

            dup2(m_slaveFd, STDIN_FILENO);
            dup2(m_slaveFd, STDOUT_FILENO);
            dup2(m_slaveFd, STDERR_FILENO);
            if (m_slaveFd > 2) {
                close(m_slaveFd);
            }

            setenv("TERM", "xterm-256color", 1);
            setenv("DEBIAN_FRONTEND", "readline", 1);
            QByteArray program = cmd.first().toLocal8Bit();
            char **argv = new char*[cmd.size() + 1];
            for (int i = 0; i < cmd.size(); ++i) {
                QByteArray arg = cmd[i].toLocal8Bit();
                argv[i] = strdup(arg.constData());
            }
            argv[cmd.size()] = nullptr;

            execvp(program.constData(), argv);
            _exit(127);
        }

        close(m_slaveFd);
        m_slaveFd = -1;
        struct pollfd pfd;
        pfd.fd = m_masterFd;
        pfd.events = POLLIN;
        QByteArray buffer;
        char readBuffer[4096];
        int status;
        pid_t result;
        while (true) {
            result = waitpid(m_childPid, &status, WNOHANG);
            if (result != 0) {
                break;
            }

            int pollResult = poll(&pfd, 1, 50);
            if (pollResult > 0 && (pfd.revents & POLLIN)) {
                ssize_t bytesRead = read(m_masterFd, readBuffer, sizeof(readBuffer) - 1);
                if (bytesRead > 0) {
                    readBuffer[bytesRead] = '\0';
                    buffer.append(readBuffer, bytesRead);
                    QString output = QString::fromUtf8(buffer);
                    while (output.contains('\n') || output.contains('\r')) {
                        int nlPos = output.indexOf('\n');
                        int crPos = output.indexOf('\r');
                        int pos = -1;
                        if (nlPos >= 0 && crPos >= 0) {
                            pos = qMin(nlPos, crPos);
                        } else if (nlPos >= 0) {
                            pos = nlPos;
                        } else if (crPos >= 0) {
                            pos = crPos;
                        }

                        if (pos >= 0) {
                            QString line = output.left(pos);
                            if (!line.isEmpty()) {
                                checkForChrootPrompt(line);
                                emit progressUpdated(line);
                            }

                            if (output[pos] == '\r' && pos + 1 < output.length() && output[pos + 1] == '\n') {
                                output = output.mid(pos + 2);
                            } else {
                                output = output.mid(pos + 1);
                            }
                            buffer = output.toUtf8();
                        } else {
                            break;
                        }
                    }

                    if (!output.isEmpty() && !output.contains('\n') && !output.contains('\r')) {
                        if (output.contains(':') || output.contains('?')) {
                            checkForChrootPrompt(output);
                            emit progressUpdated(output);
                            buffer.clear();
                        }
                    }
                } else if (bytesRead == -1 && errno != EAGAIN && errno != EWOULDBLOCK) {
                    break;
                }
            }

            QThread::msleep(10);
        }

        QThread::msleep(100);
        while (true) {
            ssize_t bytesRead = read(m_masterFd, readBuffer, sizeof(readBuffer) - 1);
            if (bytesRead <= 0) break;
            readBuffer[bytesRead] = '\0';
            buffer.append(readBuffer, bytesRead);
        }

        if (!buffer.isEmpty()) {
            QString remaining = QString::fromUtf8(buffer).trimmed();
            if (!remaining.isEmpty()) {
                emit progressUpdated(remaining);
            }
        }

        if (result == -1) {
            emit finished(false, QString("failed to wait for process: %1").arg(strerror(errno)));
        } else if (WIFEXITED(status)) {
            int exitCode = WEXITSTATUS(status);
            if (exitCode == 0) {
                emit progressUpdated("Installation completed successfully!");
                emit finished(true, "Installation completed successfully");
            } else {
                QString errorMsg = QString("Installation failed with exit code %1").arg(exitCode);
                emit progressUpdated(errorMsg);
                emit finished(false, errorMsg);
            }
        } else if (WIFSIGNALED(status)) {
            int signal = WTERMSIG(status);
            QString errorMsg = QString("installation process killed by signal %1").arg(signal);
            emit progressUpdated(errorMsg);
            emit finished(false, errorMsg);
        }

    } catch (const std::exception &e) {
        QString errorMsg = QString("installation error: %1").arg(e.what());
        emit progressUpdated(errorMsg);
        emit finished(false, errorMsg);
    }

    cleanup();
}

void InstallWorker::checkForChrootPrompt(const QString &message)
{
    if (message.contains("Do you want to chroot into slot") &&
        message.contains("(y/N)") &&
        !m_waitingForChrootResponse) {
        m_waitingForChrootResponse = true;
    emit chrootPromptDetected();
        }
}

void InstallWorker::respondToChrootPrompt(bool accepted)
{
    if (m_waitingForChrootResponse) {
        m_waitingForChrootResponse = false;
        if (accepted) {
            sendInput("y");
            m_inChroot = true;
            emit chrootEntered();
        } else {
            sendInput("n");
        }
    }
}

void InstallWorker::sendInput(const QString &text)
{
    QMutexLocker locker(&m_inputMutex);
    if (m_masterFd < 0) {
        qDebug() << "ERROR: invalid master FD";
        return;
    }

    if (m_childPid <= 0) {
        qDebug() << "ERROR: invalid child PID";
        return;
    }

    int killResult = kill(m_childPid, 0);
    if (killResult == -1 && errno == ESRCH) {
        qDebug() << "ERROR: child process no longer exists";
        return;
    }

    QByteArray data = text.toUtf8();
    if (!text.endsWith('\n') && !text.endsWith('\r')) {
        data.append('\n');
    }

    ssize_t totalWritten = 0;
    const char *ptr = data.constData();
    ssize_t remaining = data.size();
    while (remaining > 0) {
        ssize_t written = write(m_masterFd, ptr, remaining);
        if (written > 0) {
            totalWritten += written;
            ptr += written;
            remaining -= written;
        } else if (written == -1) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                struct pollfd pfd;
                pfd.fd = m_masterFd;
                pfd.events = POLLOUT;
                int ret = poll(&pfd, 1, 1000);
                if (ret <= 0) {
                    break;
                }
            } else if (errno == EINTR) {
                continue;
            } else {
                break;
            }
        } else {
            break;
        }
    }
    tcdrain(m_masterFd);
}

void InstallWorker::sendConfigs()
{
    QStringList commands = {
        QString("locale-gen %1 || true").arg(m_locale),
        QString("localectl set-locale LANG=%1 || true").arg(m_locale),
        QString("timedatectl set-timezone %1 || true").arg(m_timezone),
        QString("localectl set-keymap %1 || true").arg(m_keyboard),
        QString("usermod -l %1 user").arg(m_username),
        QString("usermod -d /home/%1 -m %1").arg(m_username),
        QString("usermod -c \"%1\" %2").arg(m_fullname, m_username),
        QString("echo '%1:%2' | chpasswd").arg(m_username, m_password),
        QString("echo 'root:%1' | chpasswd").arg(m_rootPassword)
    };

    for (const QString &cmd : commands) {
        sendInput(cmd);
        QThread::msleep(200);
    }
}
