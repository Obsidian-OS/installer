#include "ObsidianOSInstaller.h"
#include <QApplication>
#include <QDir>

ObsidianOSInstaller::ObsidianOSInstaller(QWidget *parent)
    : QMainWindow(parent)
    , m_currentPage(0)
    , m_stepIndicator(nullptr)
    , m_stackedWidget(nullptr)
    , m_backButton(nullptr)
    , m_nextButton(nullptr)
    , m_installButton(nullptr)
{
    initUI();
    setupPages();
}

void ObsidianOSInstaller::initUI()
{
    setWindowTitle("ObsidianOS Installer");
    setMinimumSize(800, 700);
    resize(800, 700);
    QPixmap appIcon(":/logo.svg");
    if (appIcon.isNull()) {
        appIcon = QPixmap("/usr/share/pixmaps/obsidianos.png");
    }
    if (!appIcon.isNull()) {
        setWindowIcon(QIcon(appIcon));
    }

    QWidget *centralWidget = new QWidget();
    setCentralWidget(centralWidget);
    QVBoxLayout *mainLayout = new QVBoxLayout(centralWidget);
    mainLayout->setContentsMargins(0, 0, 0, 0);
    mainLayout->setSpacing(0);

    QStringList steps = {
        "Welcome", "Disk", "Type", "Options", "Image",
        "Locale", "Time", "Keyboard", "User", "Summary",
        "Install", "Done"
    };
    m_stepIndicator = new StepIndicator(steps);
    m_stepIndicator->setObjectName("step-indicator");

    QWidget *contentWidget = new QWidget();
    QVBoxLayout *contentLayout = new QVBoxLayout(contentWidget);
    contentLayout->setContentsMargins(0, 0, 0, 0);

    m_stackedWidget = new QStackedWidget();

    QWidget *buttonBar = new QWidget();
    buttonBar->setObjectName("button-bar");
    QHBoxLayout *buttonLayout = new QHBoxLayout(buttonBar);
    buttonLayout->setContentsMargins(24, 16, 24, 16);
    buttonLayout->setSpacing(12);

    m_backButton = new QPushButton("Back");
    m_backButton->setObjectName("nav-button");
    m_backButton->setIcon(QIcon::fromTheme("go-previous"));
    connect(m_backButton, &QPushButton::clicked, this, &ObsidianOSInstaller::goBack);
    m_backButton->setEnabled(false);

    m_nextButton = new QPushButton("Continue");
    m_nextButton->setObjectName("nav-button-primary");
    m_nextButton->setIcon(QIcon::fromTheme("go-next"));
    m_nextButton->setLayoutDirection(Qt::RightToLeft);
    connect(m_nextButton, &QPushButton::clicked, this, &ObsidianOSInstaller::goNext);

    m_installButton = new QPushButton("Install");
    m_installButton->setObjectName("install-button");
    m_installButton->setIcon(QIcon::fromTheme("system-software-install"));
    connect(m_installButton, &QPushButton::clicked, this, &ObsidianOSInstaller::startInstallation);
    m_installButton->hide();

    buttonLayout->addWidget(m_backButton);
    buttonLayout->addStretch();
    buttonLayout->addWidget(m_installButton);
    buttonLayout->addWidget(m_nextButton);
    contentLayout->addWidget(m_stackedWidget, 1);
    contentLayout->addWidget(buttonBar);
    mainLayout->addWidget(m_stepIndicator);
    mainLayout->addWidget(contentWidget, 1);
}

void ObsidianOSInstaller::setupPages()
{
    m_pages = {
        new WelcomePage(),
        new DiskSelectionPage(),
        new DualBootPage(),
        new AdvancedOptionsPage(),
        new SystemImagePage(),
        new LocalePage(),
        new TimezonePage(),
        new KeyboardPage(),
        new UserPage(),
        new SummaryPage(),
        new InstallationPage(),
        new FinishedPage()
    };

    for (QWidget *page : m_pages) {
        m_stackedWidget->addWidget(page);
    }
}

void ObsidianOSInstaller::goBack()
{
    if (m_currentPage > 0) {
        m_currentPage--;
        m_stackedWidget->setCurrentIndex(m_currentPage);
        m_stepIndicator->setCurrentStep(m_currentPage);
        updateButtons();
    }
}

void ObsidianOSInstaller::goNext()
{
    validateCurrentPage();
    if (m_currentPage == 1) {
        DiskSelectionPage *diskPage = qobject_cast<DiskSelectionPage*>(m_pages[1]);
        QString selectedDisk = diskPage->getSelectedDisk();
        if (selectedDisk.isEmpty() || selectedDisk == "ERROR") {
            QMessageBox::warning(this, "Validation Error", "Please select a valid disk for installation.");
            return;
        }
    }
    if (m_currentPage == 8) {
        UserPage *userPage = qobject_cast<UserPage*>(m_pages[8]);
        QPair<bool, QString> result = userPage->validate();
        if (!result.first) {
            QMessageBox::warning(this, "Validation Error", result.second);
            return;
        }
    }
    if (m_currentPage < m_pages.size() - 1) {
        m_currentPage++;
        m_stackedWidget->setCurrentIndex(m_currentPage);
        m_stepIndicator->setCurrentStep(m_currentPage);
        updateButtons();
        if (m_currentPage == 9) {
            updateSummary();
        }
    }
}

void ObsidianOSInstaller::validateCurrentPage()
{
    if (m_currentPage == 1) {
        DiskSelectionPage *diskPage = qobject_cast<DiskSelectionPage*>(m_pages[1]);
        QString selectedDisk = diskPage->getSelectedDisk();
        if (selectedDisk.isEmpty() || selectedDisk == "ERROR") {
            QMessageBox::warning(this, "Validation Error", "Please select a valid disk for installation.");
            return;
        }
    }
    if (m_currentPage == 8) {
        UserPage *userPage = qobject_cast<UserPage*>(m_pages[8]);
        QPair<bool, QString> result = userPage->validate();
        if (!result.first) {
            QMessageBox::warning(this, "Validation Error", result.second);
            return;
        }
    }
}

void ObsidianOSInstaller::updateButtons()
{
    m_backButton->setEnabled(m_currentPage > 0 && m_currentPage < 10);

    if (m_currentPage == 9) {
        m_nextButton->hide();
        m_installButton->show();
    } else if (m_currentPage == 10) {
        m_nextButton->hide();
        m_installButton->hide();
        m_backButton->setEnabled(false);
    } else if (m_currentPage >= 11) {
        m_nextButton->show();
        m_nextButton->setText("Finish");
        m_nextButton->setIcon(QIcon::fromTheme("application-exit"));
        m_installButton->hide();
        m_backButton->setEnabled(false);
        disconnect(m_nextButton, &QPushButton::clicked, this, &ObsidianOSInstaller::goNext);
        connect(m_nextButton, &QPushButton::clicked, this, &ObsidianOSInstaller::close);
    } else {
        m_nextButton->show();
        m_nextButton->setText("Continue");
        m_nextButton->setIcon(QIcon::fromTheme("go-next"));
        m_installButton->hide();
    }
}

void ObsidianOSInstaller::updateSummary()
{
    DiskSelectionPage *diskPage = qobject_cast<DiskSelectionPage*>(m_pages[1]);
    DualBootPage *bootPage = qobject_cast<DualBootPage*>(m_pages[2]);
    AdvancedOptionsPage *advancedPage = qobject_cast<AdvancedOptionsPage*>(m_pages[3]);
    SystemImagePage *imagePage = qobject_cast<SystemImagePage*>(m_pages[4]);
    LocalePage *localePage = qobject_cast<LocalePage*>(m_pages[5]);
    TimezonePage *tzPage = qobject_cast<TimezonePage*>(m_pages[6]);
    KeyboardPage *kbPage = qobject_cast<KeyboardPage*>(m_pages[7]);
    UserPage *userPage = qobject_cast<UserPage*>(m_pages[8]);
    SummaryPage *summaryPage = qobject_cast<SummaryPage*>(m_pages[9]);

    summaryPage->updateSummary(
        diskPage->getSelectedDisk(),
        bootPage->getSelectedOption(),
        advancedPage->getPartitionConfig(),
        imagePage->getSelectedImage(),
        localePage->getSelectedLocale(),
        tzPage->getSelectedTimezone(),
        kbPage->getSelectedKeyboard(),
        userPage->getFullname(),
        userPage->getUsername()
    );
}

void ObsidianOSInstaller::startInstallation()
{
    m_currentPage = 10;
    m_stackedWidget->setCurrentIndex(m_currentPage);
    m_stepIndicator->setCurrentStep(m_currentPage);
    updateButtons();

    DualBootPage *bootPage = qobject_cast<DualBootPage*>(m_pages[2]);
    bool dualBootStatus = bootPage->getSelectedOption() == "alongside";

    DiskSelectionPage *diskPage = qobject_cast<DiskSelectionPage*>(m_pages[1]);
    AdvancedOptionsPage *advancedPage = qobject_cast<AdvancedOptionsPage*>(m_pages[3]);
    SystemImagePage *imagePage = qobject_cast<SystemImagePage*>(m_pages[4]);
    LocalePage *localePage = qobject_cast<LocalePage*>(m_pages[5]);
    TimezonePage *tzPage = qobject_cast<TimezonePage*>(m_pages[6]);
    KeyboardPage *kbPage = qobject_cast<KeyboardPage*>(m_pages[7]);
    UserPage *userPage = qobject_cast<UserPage*>(m_pages[8]);
    InstallationPage *installationPage = qobject_cast<InstallationPage*>(m_pages[10]);

    connect(installationPage, &InstallationPage::installationComplete, this, &ObsidianOSInstaller::installationFinished);

    installationPage->startInstallation(
        diskPage->getSelectedDisk(),
        imagePage->getSelectedImage(),
        advancedPage->getPartitionConfig(),
        dualBootStatus,
        advancedPage->getFilesystemType(),
        advancedPage->getSecureBootEnabled(),
        localePage->getSelectedLocale(),
        tzPage->getSelectedTimezone(),
        kbPage->getSelectedKeyboard(),
        userPage->getFullname(),
        userPage->getUsername(),
        userPage->getPassword(),
        userPage->getRootPassword()
    );
}

void ObsidianOSInstaller::installationFinished(bool success, const QString &message)
{
    if (success) {
        m_currentPage = 11;
        m_stackedWidget->setCurrentIndex(m_currentPage);
        m_stepIndicator->setCurrentStep(m_currentPage);
        updateButtons();

        FinishedPage *finishedPage = qobject_cast<FinishedPage*>(m_pages[11]);
        connect(finishedPage, &FinishedPage::restartSystem, this, &ObsidianOSInstaller::restartSystem);
        connect(finishedPage, &FinishedPage::showLog, this, &ObsidianOSInstaller::showLog);
    } else {
        QMessageBox::critical(this, "Installation Failed", QString("Installation failed: %1").arg(message));
    }
}

void ObsidianOSInstaller::restartSystem()
{
    QMessageBox::StandardButton reply = QMessageBox::question(
        this, "Restart System", "Are you sure you want to restart the system now?",
        QMessageBox::Yes | QMessageBox::No, QMessageBox::Yes
    );
    if (reply == QMessageBox::Yes) {
        QProcess::startDetached("reboot");
        close();
    }
}

void ObsidianOSInstaller::showLog()
{
    InstallationPage *installationPage = qobject_cast<InstallationPage*>(m_pages[10]);
    QString logText = installationPage->findChild<QTextEdit*>("log-output")->toPlainText();

    QDialog *dialog = new QDialog(this);
    dialog->setWindowTitle("Installation Log");
    dialog->resize(700, 500);
    QVBoxLayout *layout = new QVBoxLayout(dialog);
    layout->setContentsMargins(16, 16, 16, 16);

    QTextEdit *textEdit = new QTextEdit();
    textEdit->setPlainText(logText);
    textEdit->setReadOnly(true);
    textEdit->setFont(QFont("Monospace", 9));
    layout->addWidget(textEdit);

    QPushButton *closeButton = new QPushButton("Close");
    connect(closeButton, &QPushButton::clicked, dialog, &QDialog::accept);
    layout->addWidget(closeButton);

    dialog->exec();
}

#include "ObsidianOSInstaller.moc"
