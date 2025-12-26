#ifndef PAGES_H
#define PAGES_H
#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QListWidget>
#include <QListWidgetItem>
#include <QLineEdit>
#include <QRadioButton>
#include <QButtonGroup>
#include <QSpinBox>
#include <QComboBox>
#include <QTextEdit>
#include <QProgressBar>
#include <QPushButton>
#include <QGridLayout>
#include <QScrollArea>
#include <QFrame>
#include <QPixmap>
#include <QIcon>
#include <QMessageBox>
#include <QProcess>
#include <QDir>
#include <QFileInfo>
#include <QStandardPaths>
#include <QRegularExpression>
#include "InstallWorker.h"
class WelcomePage : public QWidget
{
    Q_OBJECT

public:
    explicit WelcomePage(QWidget *parent = nullptr);
};

class DiskSelectionPage : public QWidget
{
    Q_OBJECT

public:
    explicit DiskSelectionPage(QWidget *parent = nullptr);
    QString getSelectedDisk() const;

private slots:
    void scanDisks();
    void onDiskSelected(QListWidgetItem *item);

private:
    QString m_selectedDisk;
    QListWidget *m_diskList;
};

class DualBootPage : public QWidget
{
    Q_OBJECT

public:
    explicit DualBootPage(QWidget *parent = nullptr);
    QString getSelectedOption() const;

private:
    QRadioButton *m_eraseOption;
    QRadioButton *m_alongsideOption;
    QButtonGroup *m_buttonGroup;
};

class AdvancedOptionsPage : public QWidget
{
    Q_OBJECT

public:
    explicit AdvancedOptionsPage(QWidget *parent = nullptr);
    QVariantMap getPartitionConfig() const;
    QString getFilesystemType() const;

private:
    QSpinBox *m_rootfsSize;
    QSpinBox *m_espSize;
    QSpinBox *m_etcAbSize;
    QSpinBox *m_varAbSize;
    QComboBox *m_filesystemTypeCombo;
};

class SystemImagePage : public QWidget
{
    Q_OBJECT

public:
    explicit SystemImagePage(QWidget *parent = nullptr);
    QString getSelectedImage() const;

private slots:
    void scanImages();
    void onImageSelected(QListWidgetItem *item);

private:
    QString m_selectedImage;
    QListWidget *m_imageList;
};

class LocalePage : public QWidget
{
    Q_OBJECT

public:
    explicit LocalePage(QWidget *parent = nullptr);
    QString getSelectedLocale() const;

private slots:
    void filterLocales();
    void onLocaleSelected(QListWidgetItem *item);

private:
    QString m_selectedLocale;
    QLineEdit *m_searchEdit;
    QListWidget *m_localeList;
};

class TimezonePage : public QWidget
{
    Q_OBJECT

public:
    explicit TimezonePage(QWidget *parent = nullptr);
    QString getSelectedTimezone() const;

private slots:
    void filterTimezones();
    void onTzSelected(QListWidgetItem *item);

private:
    QString m_selectedTimezone;
    QLineEdit *m_searchEdit;
    QListWidget *m_tzList;
};

class UserPage : public QWidget
{
    Q_OBJECT

public:
    explicit UserPage(QWidget *parent = nullptr);
    QString getFullname() const;
    QString getUsername() const;
    QString getPassword() const;
    QString getRootPassword() const;
    QPair<bool, QString> validate() const;

private:
    QLineEdit *m_fullnameEdit;
    QLineEdit *m_usernameEdit;
    QLineEdit *m_passwordEdit;
    QLineEdit *m_confirmEdit;
    QLineEdit *m_rootPasswordEdit;
    QLineEdit *m_rootConfirmEdit;
};

class KeyboardPage : public QWidget
{
    Q_OBJECT

public:
    explicit KeyboardPage(QWidget *parent = nullptr);
    QString getSelectedKeyboard() const;

private slots:
    void filterKeyboards();
    void onKbSelected(QListWidgetItem *item);

private:
    QString m_selectedKeyboard;
    QLineEdit *m_searchEdit;
    QListWidget *m_kbList;
};

class SummaryPage : public QWidget
{
    Q_OBJECT

public:
    explicit SummaryPage(QWidget *parent = nullptr);
    void updateSummary(const QString &disk, const QString &bootOption, const QVariantMap &partitionConfig, const QString &image, const QString &locale, const QString &timezone, const QString &keyboard, const QString &fullname, const QString &username);

private:
    QGridLayout *m_summaryGrid;
    QMap<QString, QLabel*> m_summaryItems;
};

class InstallationPage : public QWidget
{
    Q_OBJECT

public:
    explicit InstallationPage(QWidget *parent = nullptr);
    void startInstallation(const QString &disk, const QString &image, const QVariantMap &partitionConfig, bool dualBoot, const QString &filesystemType, const QString &locale, const QString &timezone, const QString &keyboard, const QString &fullname, const QString &username, const QString &password, const QString &rootPassword);

signals:
    void installationComplete(bool success, const QString &message);

private slots:
    void sendInput();
    void sendYN(const QString &choice);
    void updateProgress(const QString &message);
    void installationFinished(bool success, const QString &message);
    void onChrootEntered();

private:
    QLabel *m_statusLabel;
    QProgressBar *m_progressBar;
    QTextEdit *m_logText;
    QLabel *m_questionLabel;
    QPushButton *m_yesButton;
    QPushButton *m_noButton;
    QLineEdit *m_inputField;
    QPushButton *m_sendButton;
    bool m_isYNPromptActive;

    QString m_selectedLocale;
    QString m_selectedTimezone;
    QString m_selectedKeyboard;
    QString m_selectedFullname;
    QString m_selectedUsername;
    QString m_selectedPassword;
    QString m_selectedRootPassword;
    InstallWorker *m_worker = nullptr;
};

class FinishedPage : public QWidget
{
    Q_OBJECT

public:
    explicit FinishedPage(QWidget *parent = nullptr);

signals:
    void restartSystem();
    void showLog();

private:
    QPushButton *m_restartButton;
    QPushButton *m_showLogButton;
};

#endif
