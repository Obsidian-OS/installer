#include "InstallWorker.h"
#include "Common.h"
#include <QProcess>
#include <QDebug>
#include <QStandardPaths>
#include <QApplication>
#include <cstdlib>

InstallWorker::InstallWorker(const QString &disk, const QString &image, int rootfsSize, int espSize, int etcSize, int varSize, bool dualBoot, const QString &filesystemType, const QString &locale, const QString &timezone, const QString &keyboard, const QString &fullname, const QString &username, const QString &password, const QString &rootPassword, QObject *parent)
    : QThread(parent)
    , m_disk(disk)
    , m_image(image)
    , m_rootfsSize(rootfsSize)
    , m_espSize(espSize)
    , m_etcSize(etcSize)
    , m_varSize(varSize)
    , m_dualBoot(dualBoot)
    , m_filesystemType(filesystemType)
    , m_locale(locale)
    , m_timezone(timezone)
    , m_keyboard(keyboard)
    , m_fullname(fullname)
    , m_username(username)
    , m_password(password)
    , m_rootPassword(rootPassword)
    , m_process(nullptr)
    , m_inChroot(false)
{
}

InstallWorker::~InstallWorker()
{
    if (m_process) {
        m_process->kill();
        m_process->deleteLater();
    }
}

void InstallWorker::run()
{
    try {
        QStringList cmd;
        bool testMode = QStandardPaths::findExecutable("obsidianctl").isEmpty() || isTestMode();
        
        if (testMode) {
            cmd = QStringList() << "sh" << "-c" << 
                "echo \"Test running...\"; sleep 1; "
                "echo \"Partitioning disk...\"; sleep 1; "
                "echo \"Installing system image...\"; sleep 2; "
                "echo \"Configuring bootloader...\"; sleep 1; "
                "read -p \"Do you want to proceed (y/N): \" answer; echo \"User answered: $answer\"; "
                "sleep 5; "
                "echo \"Installation complete\"";
            emit progressUpdated("Starting installation...");
        } else {
            cmd = QStringList() << "sudo" << "-S" << "obsidianctl" << "install" << m_disk << m_image
                << "--rootfs-size" << QString::number(m_rootfsSize)
                << "--esp-size" << QString::number(m_espSize)
                << "--etc-size" << QString::number(m_etcSize)
                << "--var-size" << QString::number(m_varSize);
            
            if (m_dualBoot) {
                cmd << "--dual-boot";
            }
            if (m_filesystemType == "f2fs") {
                cmd << "--use-f2fs";
            }
            emit progressUpdated("Starting installation...");
        }

        m_process = new QProcess();
        m_process->setProgram(cmd.first());
        m_process->setArguments(cmd.mid(1));
        
        m_process->setInputChannelMode(QProcess::ManagedInputChannel);
        m_process->setProcessChannelMode(QProcess::MergedChannels);
        
        connect(m_process, &QProcess::readyReadStandardOutput, [this]() {
            QString data = QString::fromLocal8Bit(m_process->readAllStandardOutput());
            emit progressUpdated(data);
        });
        
        connect(m_process, &QProcess::readyReadStandardError, [this]() {
            QString data = QString::fromLocal8Bit(m_process->readAllStandardError());
            emit progressUpdated(data);
        });
        
        m_process->start();
        
        if (!m_process->waitForStarted()) {
            emit finished(false, "Failed to start installation process");
            return;
        }

        m_process->waitForFinished(-1);
        
        if (m_process->exitCode() == 0) {
            emit progressUpdated("Installation completed successfully!");
            emit finished(true, "Installation completed successfully");
        } else {
            QString errorMsg = QString("Installation failed with exit code %1").arg(m_process->exitCode());
            emit progressUpdated(errorMsg);
            emit finished(false, errorMsg);
        }
        
    } catch (const std::exception &e) {
        QString errorMsg = QString("Installation error: %1").arg(e.what());
        emit progressUpdated(errorMsg);
        emit finished(false, errorMsg);
    }
    
    if (m_process) {
        m_process->deleteLater();
        m_process = nullptr;
    }
}

void InstallWorker::sendInput(const QString &text)
{
    if (m_process && m_process->state() == QProcess::Running) {
        QString input = text + "\n";
        m_process->write(input.toLocal8Bit());
    }
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
    }
}

