#ifndef INSTALLWORKER_H
#define INSTALLWORKER_H

#include <QThread>
#include <QString>
#include <QMutex>
#include <sys/wait.h>

class InstallWorker : public QThread
{
    Q_OBJECT

public:
    explicit InstallWorker(const QString &disk, const QString &image, int rootfsSize, int espSize, int etcSize, int varSize, bool dualBoot, const QString &filesystemType, bool secureBootEnabled, const QString &locale, const QString &timezone, const QString &keyboard, const QString &fullname, const QString &username, const QString &password, const QString &rootPassword, QObject *parent = nullptr);
    ~InstallWorker();
    void sendInput(const QString &text);
    void sendConfigs();
    void respondToChrootPrompt(bool accepted);

signals:
    void progressUpdated(const QString &message);
    void finished(bool success, const QString &message);
    void chrootEntered();
    void chrootPromptDetected();

protected:
    void run() override;

private:
    bool setupPty();
    void cleanup();
    void checkForChrootPrompt(const QString &message);
    QString m_disk;
    QString m_image;
    int m_rootfsSize;
    int m_espSize;
    int m_etcSize;
    int m_varSize;
    bool m_dualBoot;
    QString m_filesystemType;
    bool m_secureBootEnabled;
    QString m_locale;
    QString m_timezone;
    QString m_keyboard;
    QString m_fullname;
    QString m_username;
    QString m_password;
    QString m_rootPassword;
    bool m_inChroot;
    int m_masterFd;
    int m_slaveFd;
    pid_t m_childPid;
    QMutex m_inputMutex;
    bool m_waitingForChrootResponse;
};

#endif
