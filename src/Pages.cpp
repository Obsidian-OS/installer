#include "Pages.h"
#include "UIComponents.h"
#include "InstallWorker.h"
#include "Common.h"
#include <QApplication>
#include <QDir>
#include <QStandardPaths>
#include <QProcess>
#include <QFileInfo>
#include <QRegularExpression>
#include <QDialog>
#include <QVBoxLayout>
#include <QFont>

WelcomePage::WelcomePage(QWidget *parent)
    : QWidget(parent)
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setAlignment(Qt::AlignCenter);
    layout->setSpacing(24);
    layout->setContentsMargins(60, 40, 60, 40);
    QLabel *logoLabel = new QLabel();
    QPixmap pixmap(":/logo.svg");
    if (pixmap.isNull()) {
        pixmap = QPixmap("/usr/share/pixmaps/obsidianos.png");
    }
    if (!pixmap.isNull()) {
        QPixmap scaledPixmap = pixmap.scaled(180, 180, Qt::KeepAspectRatio, Qt::SmoothTransformation);
        logoLabel->setPixmap(scaledPixmap);
    }
    logoLabel->setAlignment(Qt::AlignCenter);
    QLabel *title = new QLabel("Welcome to ObsidianOS");
    title->setObjectName("welcome-title");
    title->setAlignment(Qt::AlignCenter);
    QLabel *subtitle = new QLabel("The GNU/Linux distribution with A/B Partitioning");
    subtitle->setObjectName("welcome-subtitle");
    subtitle->setAlignment(Qt::AlignCenter);
    QSpacerItem *spacer = new QSpacerItem(20, 40, QSizePolicy::Minimum, QSizePolicy::Expanding);
    layout->addWidget(logoLabel);
    layout->addWidget(title);
    layout->addWidget(subtitle);
}

DiskSelectionPage::DiskSelectionPage(QWidget *parent)
    : QWidget(parent)
    , m_selectedDisk()
    , m_diskList(nullptr)
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setSpacing(20);
    layout->setContentsMargins(40, 30, 40, 30);
    QLabel *header = new QLabel("Select Installation Disk");
    header->setObjectName("page-header");
    QLabel *desc = new QLabel("Choose the disk where ObsidianOS will be installed. All data on the selected disk will be erased.");
    desc->setObjectName("page-description");
    desc->setWordWrap(true);
    ModernCard *card = new ModernCard();
    QVBoxLayout *cardLayout = new QVBoxLayout(card);
    cardLayout->setSpacing(16);
    cardLayout->setContentsMargins(20, 20, 20, 20);
    m_diskList = new QListWidget();
    m_diskList->setObjectName("selection-list");
    connect(m_diskList, &QListWidget::itemClicked, this, &DiskSelectionPage::onDiskSelected);
    m_diskList->setMinimumHeight(200);
    cardLayout->addWidget(m_diskList);
    QWidget *warningWidget = new QWidget();
    warningWidget->setObjectName("warning-box");
    QHBoxLayout *warningLayout = new QHBoxLayout(warningWidget);
    warningLayout->setContentsMargins(16, 12, 16, 12);
    warningLayout->setSpacing(12);
    QLabel *warningIcon = new QLabel();
    warningIcon->setPixmap(style()->standardIcon(QStyle::SP_MessageBoxWarning).pixmap(24, 24));
    QLabel *warningText = new QLabel("Warning: All data on the selected disk will be permanently erased!");
    warningText->setObjectName("warning-text");
    warningText->setWordWrap(true);
    warningLayout->addWidget(warningIcon);
    warningLayout->addWidget(warningText, 1);
    layout->addWidget(header);
    layout->addWidget(desc);
    layout->addWidget(card);
    layout->addWidget(warningWidget);
    layout->addStretch();
    scanDisks();
}

QString DiskSelectionPage::getSelectedDisk() const
{
    return m_selectedDisk;
}

void DiskSelectionPage::scanDisks()
{
    m_diskList->clear();
    bool testMode = QStandardPaths::findExecutable("obsidianctl").isEmpty() || isTestMode();
    if (testMode) {
        QVector<QPair<QString, QPair<QString, QString>>> dummyDisks = {
            {"sda", {"500G", "Test SSD"}},
            {"sdb", {"1T", "Test HDD"}},
            {"nvme0n1", {"256G", "Test NVMe"}}
        };

        for (const auto &disk : dummyDisks) {
            QListWidgetItem *item = new QListWidgetItem();
            item->setText(QString("  /dev/%1  •  %2  •  %3").arg(disk.first, disk.second.first, disk.second.second));
            item->setIcon(QIcon::fromTheme("drive-harddisk"));
            item->setData(Qt::UserRole, QString("/dev/%1").arg(disk.first));
            item->setSizeHint(item->sizeHint().expandedTo(item->sizeHint()));
            m_diskList->addItem(item);
        }
        return;
    }

    QProcess process;
    process.start("lsblk", {"-d", "-n", "-o", "NAME,SIZE,MODEL"});
    process.waitForFinished();
    QString output = process.readAllStandardOutput();
    QStringList lines = output.split('\n');
    for (const QString &line : lines) {
        if (!line.isEmpty() && !line.startsWith("loop")) {
            QStringList parts = line.split(QRegularExpression("\\s+"), Qt::SkipEmptyParts);
            if (parts.size() >= 2) {
                QString name = parts[0];
                QString size = parts[1];
                QString model = (parts.size() > 2) ? parts[2] : "Unknown";
                QListWidgetItem *item = new QListWidgetItem();
                item->setText(QString("  /dev/%1  •  %2  •  %3").arg(name, size, model));
                item->setIcon(QIcon::fromTheme("drive-harddisk"));
                item->setData(Qt::UserRole, QString("/dev/%1").arg(name));
                m_diskList->addItem(item);
            }
        }
    }

    if (m_diskList->count() == 0) {
        QListWidgetItem *item = new QListWidgetItem("  Error detecting disks");
        item->setIcon(QIcon::fromTheme("dialog-error"));
        item->setData(Qt::UserRole, "ERROR");
        m_diskList->addItem(item);
    }
}

void DiskSelectionPage::onDiskSelected(QListWidgetItem *item)
{
    m_selectedDisk = item->data(Qt::UserRole).toString();
}

DualBootPage::DualBootPage(QWidget *parent)
    : QWidget(parent)
    , m_eraseOption(nullptr)
    , m_alongsideOption(nullptr)
    , m_buttonGroup(nullptr)
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setSpacing(20);
    layout->setContentsMargins(40, 30, 40, 30);
    QLabel *header = new QLabel("Installation Type");
    header->setObjectName("page-header");
    QLabel *desc = new QLabel("Choose how you want to install ObsidianOS on your system.");
    desc->setObjectName("page-description");
    desc->setWordWrap(true);
    m_buttonGroup = new QButtonGroup(this);
    ModernCard *eraseCard = new ModernCard();
    eraseCard->setObjectName("option-card");
    QHBoxLayout *eraseLayout = new QHBoxLayout(eraseCard);
    eraseLayout->setContentsMargins(20, 20, 20, 20);
    eraseLayout->setSpacing(16);
    QLabel *eraseIcon = new QLabel();
    eraseIcon->setPixmap(QIcon::fromTheme("drive-harddisk").pixmap(48, 48));
    QVBoxLayout *eraseTextLayout = new QVBoxLayout();
    eraseTextLayout->setSpacing(4);
    m_eraseOption = new QRadioButton("Erase disk and install ObsidianOS");
    m_eraseOption->setObjectName("option-radio");
    m_eraseOption->setChecked(true);
    QLabel *eraseDesc = new QLabel("This will remove all existing data and operating systems from the selected disk.");
    eraseDesc->setObjectName("option-desc");
    eraseDesc->setWordWrap(true);
    eraseTextLayout->addWidget(m_eraseOption);
    eraseTextLayout->addWidget(eraseDesc);
    eraseLayout->addWidget(eraseIcon);
    eraseLayout->addLayout(eraseTextLayout, 1);
    m_buttonGroup->addButton(m_eraseOption);
    ModernCard *alongsideCard = new ModernCard();
    alongsideCard->setObjectName("option-card");
    QHBoxLayout *alongsideLayout = new QHBoxLayout(alongsideCard);
    alongsideLayout->setContentsMargins(20, 20, 20, 20);
    alongsideLayout->setSpacing(16);
    QLabel *alongsideIcon = new QLabel();
    alongsideIcon->setPixmap(QIcon::fromTheme("drive-multidisk").pixmap(48, 48));
    QVBoxLayout *alongsideTextLayout = new QVBoxLayout();
    alongsideTextLayout->setSpacing(4);
    m_alongsideOption = new QRadioButton("Install alongside existing OS (Dual Boot)");
    m_alongsideOption->setObjectName("option-radio");
    QLabel *alongsideDesc = new QLabel("Keep your existing operating system and install ObsidianOS alongside it.");
    alongsideDesc->setObjectName("option-desc");
    alongsideDesc->setWordWrap(true);
    alongsideTextLayout->addWidget(m_alongsideOption);
    alongsideTextLayout->addWidget(alongsideDesc);
    alongsideLayout->addWidget(alongsideIcon);
    alongsideLayout->addLayout(alongsideTextLayout, 1);
    m_buttonGroup->addButton(m_alongsideOption);
    layout->addWidget(header);
    layout->addWidget(desc);
    layout->addSpacing(10);
    layout->addWidget(eraseCard);
    layout->addWidget(alongsideCard);
    layout->addStretch();
}

QString DualBootPage::getSelectedOption() const
{
    if (m_eraseOption->isChecked()) {
        return "erase";
    } else if (m_alongsideOption->isChecked()) {
        return "alongside";
    }
    return "erase";
}

AdvancedOptionsPage::AdvancedOptionsPage(QWidget *parent)
    : QWidget(parent)
    , m_rootfsSize(nullptr)
    , m_espSize(nullptr)
    , m_etcAbSize(nullptr)
    , m_varAbSize(nullptr)
    , m_filesystemTypeCombo(nullptr)
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setSpacing(20);
    layout->setContentsMargins(40, 30, 40, 30);
    QLabel *header = new QLabel("Advanced Options");
    header->setObjectName("page-header");
    QLabel *desc = new QLabel("Configure partition sizes and filesystem options for your installation.");
    desc->setObjectName("page-description");
    desc->setWordWrap(true);
    ModernCard *card = new ModernCard();
    QVBoxLayout *cardLayout = new QVBoxLayout(card);
    cardLayout->setContentsMargins(20, 20, 20, 20);
    QLabel *partitionLabel = new QLabel("Partition Configuration");
    partitionLabel->setObjectName("section-title");
    cardLayout->addWidget(partitionLabel);
    QGridLayout *grid = new QGridLayout();
    grid->setColumnStretch(1, 1);
    m_rootfsSize = new QSpinBox();
    m_rootfsSize->setRange(1, 9999);
    m_rootfsSize->setValue(10);
    m_rootfsSize->setSuffix(" GB");
    m_rootfsSize->setObjectName("modern-spinbox");
    grid->addWidget(new QLabel("Root Filesystem (A/B):"), 0, 0);
    grid->addWidget(m_rootfsSize, 0, 1);
    m_espSize = new QSpinBox();
    m_espSize->setRange(100, 2048);
    m_espSize->setValue(512);
    m_espSize->setSuffix(" MB");
    m_espSize->setObjectName("modern-spinbox");
    grid->addWidget(new QLabel("EFI System Partition:"), 1, 0);
    grid->addWidget(m_espSize, 1, 1);
    m_etcAbSize = new QSpinBox();
    m_etcAbSize->setRange(1, 9999);
    m_etcAbSize->setValue(1);
    m_etcAbSize->setSuffix(" GB");
    m_etcAbSize->setObjectName("modern-spinbox");
    grid->addWidget(new QLabel("etc_ab Partition (A/B):"), 2, 0);
    grid->addWidget(m_etcAbSize, 2, 1);
    m_varAbSize = new QSpinBox();
    m_varAbSize->setRange(1, 9999);
    m_varAbSize->setValue(5);
    m_varAbSize->setSuffix(" GB");
    m_varAbSize->setObjectName("modern-spinbox");
    grid->addWidget(new QLabel("var_ab Partition (A/B):"), 3, 0);
    grid->addWidget(m_varAbSize, 3, 1);
    cardLayout->addLayout(grid);
    QLabel *fsLabel = new QLabel("Filesystem Type");
    fsLabel->setObjectName("section-title");
    cardLayout->addWidget(fsLabel);
    m_filesystemTypeCombo = new QComboBox();
    m_filesystemTypeCombo->addItem("ext4 - Standard Linux filesystem");
    m_filesystemTypeCombo->addItem("f2fs - Flash-Friendly File System");
    m_filesystemTypeCombo->setObjectName("modern-combo");
    cardLayout->addWidget(m_filesystemTypeCombo);
    QWidget *infoWidget = new QWidget();
    infoWidget->setObjectName("info-box");
    QHBoxLayout *infoLayout = new QHBoxLayout(infoWidget);
    infoLayout->setContentsMargins(16, 12, 16, 12);
    infoLayout->setSpacing(12);
    QLabel *infoIcon = new QLabel();
    infoIcon->setPixmap(style()->standardIcon(QStyle::SP_MessageBoxInformation).pixmap(24, 24));
    QLabel *infoText = new QLabel("The A/B partition scheme creates duplicate partitions for seamless updates and instant rollback capability.");
    infoText->setObjectName("info-text");
    infoText->setWordWrap(true);
    infoLayout->addWidget(infoIcon);
    infoLayout->addWidget(infoText, 1);
    layout->addWidget(header);
    layout->addWidget(desc);
    layout->addWidget(card);
    layout->addWidget(infoWidget);
    layout->addStretch();
}

QVariantMap AdvancedOptionsPage::getPartitionConfig() const
{
    QVariantMap config;
    config["rootfs_size"] = QString("%1G").arg(m_rootfsSize->value());
    config["esp_size"] = QString("%1M").arg(m_espSize->value());
    config["etc_ab_size"] = QString("%1G").arg(m_etcAbSize->value());
    config["var_ab_size"] = QString("%1G").arg(m_varAbSize->value());
    return config;
}

QString AdvancedOptionsPage::getFilesystemType() const
{
    return m_filesystemTypeCombo->currentText().contains("f2fs") ? "f2fs" : "ext4";
}

SystemImagePage::SystemImagePage(QWidget *parent)
    : QWidget(parent)
    , m_selectedImage("/etc/system.sfs")
    , m_imageList(nullptr)
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setSpacing(20);
    layout->setContentsMargins(40, 30, 40, 30);
    QLabel *header = new QLabel("Select System Image");
    header->setObjectName("page-header");
    QLabel *desc = new QLabel("Choose the system image to install. The default image is recommended for most users.");
    desc->setObjectName("page-description");
    desc->setWordWrap(true);
    ModernCard *card = new ModernCard();
    QVBoxLayout *cardLayout = new QVBoxLayout(card);
    cardLayout->setSpacing(16);
    cardLayout->setContentsMargins(20, 20, 20, 20);
    m_imageList = new QListWidget();
    m_imageList->setObjectName("selection-list");
    connect(m_imageList, &QListWidget::itemClicked, this, &SystemImagePage::onImageSelected);
    m_imageList->setMinimumHeight(300);
    cardLayout->addWidget(m_imageList);
    layout->addWidget(header);
    layout->addWidget(desc);
    layout->addWidget(card);
    layout->addStretch();
    scanImages();
}

QString SystemImagePage::getSelectedImage() const
{
    return m_selectedImage;
}

void SystemImagePage::scanImages()
{
    m_imageList->clear();
    QListWidgetItem *defaultItem = new QListWidgetItem();
    defaultItem->setText("  Default System Image");
    defaultItem->setIcon(QIcon::fromTheme("package-x-generic"));
    defaultItem->setData(Qt::UserRole, "/etc/system.sfs");
    m_imageList->addItem(defaultItem);
    m_imageList->setCurrentItem(defaultItem);
    QDir preconfPath("/usr/preconf");
    if (preconfPath.exists()) {
        QStringList filters;
        filters << "*.mkobsfs";
        QFileInfoList files = preconfPath.entryInfoList(filters, QDir::Files);
        for (const QFileInfo &file : files) {
            QListWidgetItem *item = new QListWidgetItem();
            item->setText(QString("  %1").arg(file.baseName()));
            item->setIcon(QIcon::fromTheme("application-x-executable"));
            item->setData(Qt::UserRole, file.absoluteFilePath());
            m_imageList->addItem(item);
        }
    }

    QDir homePath = QDir::home();
    QStringList filters;
    filters << "*.mkobsfs" << "*.sfs";
    QFileInfoList files = homePath.entryInfoList(filters, QDir::Files);
    for (const QFileInfo &file : files) {
        QListWidgetItem *item = new QListWidgetItem();
        item->setText(QString("  %1").arg(file.fileName()));
        QString iconName = file.suffix() == "mkobsfs" ? "folder" : "media-optical";
        item->setIcon(QIcon::fromTheme(iconName));
        item->setData(Qt::UserRole, file.absoluteFilePath());
        m_imageList->addItem(item);
    }
}

void SystemImagePage::onImageSelected(QListWidgetItem *item)
{
    m_selectedImage = item->data(Qt::UserRole).toString();
}

LocalePage::LocalePage(QWidget *parent)
    : QWidget(parent)
    , m_selectedLocale("en_US.UTF-8")
    , m_searchEdit(nullptr)
    , m_localeList(nullptr)
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setSpacing(20);
    layout->setContentsMargins(40, 30, 40, 30);
    QLabel *header = new QLabel("Select Locale");
    header->setObjectName("page-header");
    QLabel *desc = new QLabel("Choose your preferred language and regional format settings.");
    desc->setObjectName("page-description");
    desc->setWordWrap(true);
    ModernCard *card = new ModernCard();
    QVBoxLayout *cardLayout = new QVBoxLayout(card);
    cardLayout->setSpacing(12);
    cardLayout->setContentsMargins(20, 20, 20, 20);
    m_searchEdit = new QLineEdit();
    m_searchEdit->setPlaceholderText("Search locales...");
    m_searchEdit->setObjectName("search-field");
    connect(m_searchEdit, &QLineEdit::textChanged, this, &LocalePage::filterLocales);
    m_searchEdit->setClearButtonEnabled(true);
    m_localeList = new QListWidget();
    m_localeList->setObjectName("selection-list");
    connect(m_localeList, &QListWidget::itemClicked, this, &LocalePage::onLocaleSelected);
    m_localeList->setMinimumHeight(300);
    QProcess process;
    process.start("ls", {"/usr/share/locale"});
    process.waitForFinished();
    QString output = process.readAllStandardOutput();
    QStringList locales = output.split('\n');
    for (const QString &loc : locales) {
        if (!loc.trimmed().isEmpty()) {
            QListWidgetItem *item = new QListWidgetItem();
            item->setText(QString("  %1").arg(loc));
            item->setIcon(QIcon::fromTheme("preferences-desktop-locale"));
            m_localeList->addItem(item);
        }
    }

    if (m_localeList->count() > 0) {
        m_localeList->setCurrentRow(0);
    }

    cardLayout->addWidget(m_searchEdit);
    cardLayout->addWidget(m_localeList);
    layout->addWidget(header);
    layout->addWidget(desc);
    layout->addWidget(card);
    layout->addStretch();
}

QString LocalePage::getSelectedLocale() const
{
    return m_selectedLocale;
}

void LocalePage::filterLocales()
{
    QString text = m_searchEdit->text().toLower();
    for (int i = 0; i < m_localeList->count(); ++i) {
        QListWidgetItem *item = m_localeList->item(i);
        item->setHidden(!item->text().toLower().contains(text));
    }
}

void LocalePage::onLocaleSelected(QListWidgetItem *item)
{
    m_selectedLocale = item->text().trimmed();
}

TimezonePage::TimezonePage(QWidget *parent)
    : QWidget(parent)
    , m_selectedTimezone("UTC")
    , m_searchEdit(nullptr)
    , m_tzList(nullptr)
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setSpacing(20);
    layout->setContentsMargins(40, 30, 40, 30);
    QLabel *header = new QLabel("Select Timezone");
    header->setObjectName("page-header");
    QLabel *desc = new QLabel("Choose your timezone to ensure correct time display.");
    desc->setObjectName("page-description");
    desc->setWordWrap(true);
    ModernCard *card = new ModernCard();
    QVBoxLayout *cardLayout = new QVBoxLayout(card);
    cardLayout->setSpacing(12);
    cardLayout->setContentsMargins(20, 20, 20, 20);
    m_searchEdit = new QLineEdit();
    m_searchEdit->setPlaceholderText("Search timezones...");
    m_searchEdit->setObjectName("search-field");
    connect(m_searchEdit, &QLineEdit::textChanged, this, &TimezonePage::filterTimezones);
    m_searchEdit->setClearButtonEnabled(true);
    m_tzList = new QListWidget();
    m_tzList->setObjectName("selection-list");
    connect(m_tzList, &QListWidget::itemClicked, this, &TimezonePage::onTzSelected);
    m_tzList->setMinimumHeight(300);
    QProcess process;
    process.start("timedatectl", {"list-timezones"});
    process.waitForFinished();
    QString output = process.readAllStandardOutput();
    QStringList timezones = output.split('\n');
    for (const QString &tz : timezones) {
        if (!tz.trimmed().isEmpty()) {
            QListWidgetItem *item = new QListWidgetItem();
            item->setText(QString("  %1").arg(tz));
            item->setIcon(QIcon::fromTheme("preferences-system-time"));
            m_tzList->addItem(item);
        }
    }

    if (m_tzList->count() > 0) {
        m_tzList->setCurrentRow(0);
    }

    cardLayout->addWidget(m_searchEdit);
    cardLayout->addWidget(m_tzList);
    layout->addWidget(header);
    layout->addWidget(desc);
    layout->addWidget(card);
    layout->addStretch();
}

QString TimezonePage::getSelectedTimezone() const
{
    return m_selectedTimezone;
}

void TimezonePage::filterTimezones()
{
    QString text = m_searchEdit->text().toLower();
    for (int i = 0; i < m_tzList->count(); ++i) {
        QListWidgetItem *item = m_tzList->item(i);
        item->setHidden(!item->text().toLower().contains(text));
    }
}

void TimezonePage::onTzSelected(QListWidgetItem *item)
{
    m_selectedTimezone = item->text().trimmed();
}

UserPage::UserPage(QWidget *parent)
    : QWidget(parent)
    , m_fullnameEdit(nullptr)
    , m_usernameEdit(nullptr)
    , m_passwordEdit(nullptr)
    , m_confirmEdit(nullptr)
    , m_rootPasswordEdit(nullptr)
    , m_rootConfirmEdit(nullptr)
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setSpacing(20);
    layout->setContentsMargins(40, 30, 40, 30);
    QLabel *header = new QLabel("Create User Account");
    header->setObjectName("page-header");
    QLabel *desc = new QLabel("Set up your user account and passwords.");
    desc->setObjectName("page-description");
    desc->setWordWrap(true);
    ModernCard *card = new ModernCard();
    QVBoxLayout *cardLayout = new QVBoxLayout(card);
    cardLayout->setSpacing(16);
    cardLayout->setContentsMargins(20, 20, 20, 20);
    QHBoxLayout *fullnameLayout = new QHBoxLayout();
    QLabel *fullnameLabel = new QLabel("Full Name:");
    fullnameLabel->setMinimumWidth(120);
    m_fullnameEdit = new QLineEdit();
    m_fullnameEdit->setText("User");
    m_fullnameEdit->setPlaceholderText("John Doe");
    m_fullnameEdit->setObjectName("user-field");
    fullnameLayout->addWidget(fullnameLabel);
    fullnameLayout->addWidget(m_fullnameEdit);
    QHBoxLayout *usernameLayout = new QHBoxLayout();
    QLabel *usernameLabel = new QLabel("Username:");
    usernameLabel->setMinimumWidth(120);
    m_usernameEdit = new QLineEdit();
    m_usernameEdit->setText("user");
    m_usernameEdit->setPlaceholderText("johndoe");
    m_usernameEdit->setObjectName("user-field");
    usernameLayout->addWidget(usernameLabel);
    usernameLayout->addWidget(m_usernameEdit);
    QHBoxLayout *passwordLayout = new QHBoxLayout();
    QLabel *passwordLabel = new QLabel("Password:");
    passwordLabel->setMinimumWidth(120);
    m_passwordEdit = new QLineEdit();
    m_passwordEdit->setEchoMode(QLineEdit::Password);
    m_passwordEdit->setPlaceholderText("Enter password");
    m_passwordEdit->setObjectName("user-field");
    passwordLayout->addWidget(passwordLabel);
    passwordLayout->addWidget(m_passwordEdit);
    QHBoxLayout *confirmLayout = new QHBoxLayout();
    QLabel *confirmLabel = new QLabel("Confirm Password:");
    confirmLabel->setMinimumWidth(120);
    m_confirmEdit = new QLineEdit();
    m_confirmEdit->setEchoMode(QLineEdit::Password);
    m_confirmEdit->setPlaceholderText("Confirm password");
    m_confirmEdit->setObjectName("user-field");
    confirmLayout->addWidget(confirmLabel);
    confirmLayout->addWidget(m_confirmEdit);
    QHBoxLayout *rootPasswordLayout = new QHBoxLayout();
    QLabel *rootPasswordLabel = new QLabel("Root Password:");
    rootPasswordLabel->setMinimumWidth(120);
    m_rootPasswordEdit = new QLineEdit();
    m_rootPasswordEdit->setEchoMode(QLineEdit::Password);
    m_rootPasswordEdit->setPlaceholderText("Enter root password");
    m_rootPasswordEdit->setObjectName("user-field");
    rootPasswordLayout->addWidget(rootPasswordLabel);
    rootPasswordLayout->addWidget(m_rootPasswordEdit);
    QHBoxLayout *rootConfirmLayout = new QHBoxLayout();
    QLabel *rootConfirmLabel = new QLabel("Confirm Root:");
    rootConfirmLabel->setMinimumWidth(120);
    m_rootConfirmEdit = new QLineEdit();
    m_rootConfirmEdit->setEchoMode(QLineEdit::Password);
    m_rootConfirmEdit->setPlaceholderText("Confirm root password");
    m_rootConfirmEdit->setObjectName("user-field");
    rootConfirmLayout->addWidget(rootConfirmLabel);
    rootConfirmLayout->addWidget(m_rootConfirmEdit);
    cardLayout->addLayout(fullnameLayout);
    cardLayout->addLayout(usernameLayout);
    cardLayout->addLayout(passwordLayout);
    cardLayout->addLayout(confirmLayout);
    cardLayout->addLayout(rootPasswordLayout);
    cardLayout->addLayout(rootConfirmLayout);
    layout->addWidget(header);
    layout->addWidget(desc);
    layout->addWidget(card);
    layout->addStretch();
}

QString UserPage::getFullname() const
{
    return m_fullnameEdit->text().trimmed().isEmpty() ? "User" : m_fullnameEdit->text().trimmed();
}

QString UserPage::getUsername() const
{
    return m_usernameEdit->text().trimmed().isEmpty() ? "user" : m_usernameEdit->text().trimmed();
}

QString UserPage::getPassword() const
{
    return m_passwordEdit->text();
}

QString UserPage::getRootPassword() const
{
    return m_rootPasswordEdit->text();
}

QPair<bool, QString> UserPage::validate() const
{
    if (getPassword().isEmpty()) {
        return qMakePair(false, "Password is required");
    }
    if (m_passwordEdit->text() != m_confirmEdit->text()) {
        return qMakePair(false, "Passwords do not match");
    }
    if (getRootPassword().isEmpty()) {
        return qMakePair(false, "Root password is required");
    }
    if (m_rootPasswordEdit->text() != m_rootConfirmEdit->text()) {
        return qMakePair(false, "Root passwords do not match");
    }
    return qMakePair(true, "");
}

KeyboardPage::KeyboardPage(QWidget *parent)
    : QWidget(parent)
    , m_selectedKeyboard("us")
    , m_searchEdit(nullptr)
    , m_kbList(nullptr)
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setSpacing(20);
    layout->setContentsMargins(40, 30, 40, 30);
    QLabel *header = new QLabel("Select Keyboard Layout");
    header->setObjectName("page-header");
    QLabel *desc = new QLabel("Choose the keyboard layout that matches your physical keyboard.");
    desc->setObjectName("page-description");
    desc->setWordWrap(true);
    ModernCard *card = new ModernCard();
    QVBoxLayout *cardLayout = new QVBoxLayout(card);
    cardLayout->setSpacing(12);
    cardLayout->setContentsMargins(20, 20, 20, 20);
    m_searchEdit = new QLineEdit();
    m_searchEdit->setPlaceholderText("Search keyboard layouts...");
    m_searchEdit->setObjectName("search-field");
    connect(m_searchEdit, &QLineEdit::textChanged, this, &KeyboardPage::filterKeyboards);
    m_searchEdit->setClearButtonEnabled(true);
    m_kbList = new QListWidget();
    m_kbList->setObjectName("selection-list");
    connect(m_kbList, &QListWidget::itemClicked, this, &KeyboardPage::onKbSelected);
    m_kbList->setMinimumHeight(300);
    QProcess process;
    process.start("localectl", {"list-keymaps"});
    process.waitForFinished();
    QString output = process.readAllStandardOutput();
    QStringList keyboards = output.split('\n');
    for (const QString &kb : keyboards) {
        if (!kb.trimmed().isEmpty()) {
            QListWidgetItem *item = new QListWidgetItem();
            item->setText(QString("  %1").arg(kb));
            item->setIcon(QIcon::fromTheme("input-keyboard"));
            m_kbList->addItem(item);
        }
    }

    if (m_kbList->count() > 0) {
        m_kbList->setCurrentRow(0);
    }

    cardLayout->addWidget(m_searchEdit);
    cardLayout->addWidget(m_kbList);
    layout->addWidget(header);
    layout->addWidget(desc);
    layout->addWidget(card);
    layout->addStretch();
}

QString KeyboardPage::getSelectedKeyboard() const
{
    return m_selectedKeyboard;
}

void KeyboardPage::filterKeyboards()
{
    QString text = m_searchEdit->text().toLower();
    for (int i = 0; i < m_kbList->count(); ++i) {
        QListWidgetItem *item = m_kbList->item(i);
        item->setHidden(!item->text().toLower().contains(text));
    }
}

void KeyboardPage::onKbSelected(QListWidgetItem *item)
{
    m_selectedKeyboard = item->text().trimmed();
}

SummaryPage::SummaryPage(QWidget *parent)
    : QWidget(parent)
    , m_summaryGrid(nullptr)
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setSpacing(20);
    layout->setContentsMargins(40, 30, 40, 30);
    QLabel *header = new QLabel("Review Installation Settings");
    header->setObjectName("page-header");
    QLabel *desc = new QLabel("Please review your settings before starting the installation.");
    desc->setObjectName("page-description");
    desc->setWordWrap(true);
    QScrollArea *scroll = new QScrollArea();
    scroll->setWidgetResizable(true);
    scroll->setObjectName("summary-scroll");
    ModernCard *card = new ModernCard();
    QVBoxLayout *cardLayout = new QVBoxLayout(card);
    cardLayout->setSpacing(16);
    cardLayout->setContentsMargins(24, 24, 24, 24);
    m_summaryGrid = new QGridLayout();
    m_summaryGrid->setSpacing(12);
    m_summaryGrid->setColumnStretch(1, 1);
    QVector<QPair<QString, QPair<QString, QString>>> items = {
        {"disk", {"drive-harddisk", "Installation Target"}},
        {"boot", {"system-run", "Installation Type"}},
        {"image", {"package-x-generic", "System Image"}},
        {"locale", {"preferences-desktop-locale", "Locale"}},
        {"timezone", {"preferences-system-time", "Timezone"}},
        {"keyboard", {"input-keyboard", "Keyboard Layout"}},
        {"user", {"user-info", "User Account"}},
        {"partitions", {"drive-multidisk", "Partition Layout"}}
    };

    for (int i = 0; i < items.size(); ++i) {
        const auto &item = items[i];
        QLabel *iconLabel = new QLabel();
        QIcon icon = QIcon::fromTheme(item.second.first);
        if (!icon.isNull()) {
            iconLabel->setPixmap(icon.pixmap(20, 20));
        }

        QLabel *nameLabel = new QLabel(item.second.second + ":");
        nameLabel->setObjectName("summary-label");
        QLabel *valueLabel = new QLabel();
        valueLabel->setObjectName("summary-value");
        valueLabel->setWordWrap(true);
        m_summaryItems[item.first] = valueLabel;
        m_summaryGrid->addWidget(iconLabel, i, 0);
        m_summaryGrid->addWidget(nameLabel, i, 1);
        m_summaryGrid->addWidget(valueLabel, i, 2);
    }

    cardLayout->addLayout(m_summaryGrid);
    scroll->setWidget(card);
    QWidget *warningWidget = new QWidget();
    warningWidget->setObjectName("warning-box");
    QHBoxLayout *warningLayout = new QHBoxLayout(warningWidget);
    warningLayout->setContentsMargins(16, 12, 16, 12);
    warningLayout->setSpacing(12);
    QLabel *warningIcon = new QLabel();
    warningIcon->setPixmap(style()->standardIcon(QStyle::SP_MessageBoxWarning).pixmap(24, 24));
    QLabel *warningText = new QLabel("Click 'Install' to begin. This process cannot be undone!");
    warningText->setObjectName("warning-text");
    warningText->setWordWrap(true);
    warningLayout->addWidget(warningIcon);
    warningLayout->addWidget(warningText, 1);
    layout->addWidget(header);
    layout->addWidget(desc);
    layout->addWidget(scroll, 1);
    layout->addWidget(warningWidget);
}

void SummaryPage::updateSummary(const QString &disk, const QString &bootOption, const QVariantMap &partitionConfig, const QString &image, const QString &locale, const QString &timezone, const QString &keyboard, const QString &fullname, const QString &username)
{
    m_summaryItems["disk"]->setText(disk.isEmpty() ? "Not selected" : disk);
    m_summaryItems["boot"]->setText(bootOption == "erase" ? "Erase disk" : "Dual boot");
    m_summaryItems["image"]->setText(image.isEmpty() ? "Default" : image);
    m_summaryItems["locale"]->setText(locale);
    m_summaryItems["timezone"]->setText(timezone);
    m_summaryItems["keyboard"]->setText(keyboard);
    m_summaryItems["user"]->setText(QString("%1 (%2)").arg(fullname, username));
    QString partitionsText = QString("ESP: %1 | Root: %2 (A/B) | etc: %3 (A/B) | var: %4 (A/B)")
        .arg(partitionConfig["esp_size"].toString())
        .arg(partitionConfig["rootfs_size"].toString())
        .arg(partitionConfig["etc_ab_size"].toString())
        .arg(partitionConfig["var_ab_size"].toString());
    m_summaryItems["partitions"]->setText(partitionsText);
}

InstallationPage::InstallationPage(QWidget *parent)
: QWidget(parent)
, m_statusLabel(nullptr)
, m_progressBar(nullptr)
, m_logText(nullptr)
, m_questionLabel(nullptr)
, m_yesButton(nullptr)
, m_noButton(nullptr)
, m_inputField(nullptr)
, m_sendButton(nullptr)
, m_isYNPromptActive(false)
, m_worker(nullptr)
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setSpacing(16);
    layout->setContentsMargins(40, 30, 40, 30);
    QLabel *header = new QLabel("Installing ObsidianOS");
    header->setObjectName("page-header");
    m_statusLabel = new QLabel("Preparing installation...");
    m_statusLabel->setObjectName("status-label");
    m_statusLabel->setAlignment(Qt::AlignCenter);
    m_progressBar = new QProgressBar();
    m_progressBar->setRange(0, 0);
    m_progressBar->setObjectName("modern-progress");
    m_progressBar->setMinimumHeight(8);
    m_progressBar->setTextVisible(false);
    ModernCard *card = new ModernCard();
    QVBoxLayout *cardLayout = new QVBoxLayout(card);
    cardLayout->setSpacing(12);
    cardLayout->setContentsMargins(16, 16, 16, 16);
    m_logText = new QTextEdit();
    m_logText->setReadOnly(true);
    m_logText->setFont(QFont("Monospace", 9));
    m_logText->setObjectName("log-output");
    m_logText->setMinimumHeight(200);
    cardLayout->addWidget(m_logText);
    ModernCard *inputCard = new ModernCard();
    inputCard->setObjectName("input-card");
    QVBoxLayout *inputLayout = new QVBoxLayout(inputCard);
    inputLayout->setSpacing(8);
    inputLayout->setContentsMargins(16, 12, 16, 12);
    m_questionLabel = new QLabel();
    m_questionLabel->setObjectName("question-label");
    m_questionLabel->hide();
    QHBoxLayout *buttonRow = new QHBoxLayout();
    buttonRow->setSpacing(12);
    m_yesButton = new QPushButton("Yes");
    m_yesButton->setObjectName("action-button");
    m_noButton = new QPushButton("No");
    m_noButton->setObjectName("action-button");
    m_yesButton->hide();
    m_noButton->hide();
    buttonRow->addWidget(m_yesButton);
    buttonRow->addWidget(m_noButton);
    buttonRow->addStretch();
    QHBoxLayout *textRow = new QHBoxLayout();
    textRow->setSpacing(8);
    m_inputField = new QLineEdit();
    m_inputField->setObjectName("command-input");
    m_inputField->setPlaceholderText("Enter command...");
    m_sendButton = new QPushButton();
    m_sendButton->setIcon(style()->standardIcon(QStyle::SP_ArrowForward));
    m_sendButton->setObjectName("send-button");
    connect(m_sendButton, &QPushButton::clicked, this, &InstallationPage::sendInput);
    textRow->addWidget(m_inputField, 1);
    textRow->addWidget(m_sendButton);
    inputLayout->addWidget(m_questionLabel);
    inputLayout->addLayout(buttonRow);
    inputLayout->addLayout(textRow);
    layout->addWidget(header);
    layout->addWidget(m_statusLabel);
    layout->addWidget(m_progressBar);
    layout->addWidget(card, 1);
    layout->addWidget(inputCard);

    connect(m_yesButton, &QPushButton::clicked, this, [this]() {
        if (m_worker) {
            m_worker->respondToChrootPrompt(true);
        }
        m_questionLabel->hide();
        m_yesButton->hide();
        m_noButton->hide();
        m_inputField->show();
        m_sendButton->show();
        m_isYNPromptActive = false;
    });

    connect(m_noButton, &QPushButton::clicked, this, [this]() {
        if (m_worker) {
            m_worker->respondToChrootPrompt(false);
        }
        m_questionLabel->hide();
        m_yesButton->hide();
        m_noButton->hide();
        m_inputField->show();
        m_sendButton->show();
        m_isYNPromptActive = false;
    });

    connect(m_inputField, &QLineEdit::returnPressed, this, &InstallationPage::sendInput);
}

void InstallationPage::startInstallation(const QString &disk, const QString &image, const QVariantMap &partitionConfig, bool dualBoot, const QString &filesystemType, const QString &locale, const QString &timezone, const QString &keyboard, const QString &fullname, const QString &username, const QString &password, const QString &rootPassword)
{
    m_statusLabel->setText("Starting installation...");
    m_logText->clear();
    m_selectedLocale = locale;
    m_selectedTimezone = timezone;
    m_selectedKeyboard = keyboard;
    m_selectedFullname = fullname;
    m_selectedUsername = username;
    m_selectedPassword = password;
    m_selectedRootPassword = rootPassword;

    if (m_worker) {
        m_worker->deleteLater();
        m_worker = nullptr;
    }

    m_worker = new InstallWorker(
        disk, image,
        partitionConfig["rootfs_size"].toString().replace("G", "").toInt(),
                                 partitionConfig["esp_size"].toString().replace("M", "").toInt(),
                                 partitionConfig["etc_ab_size"].toString().replace("G", "").toInt(),
                                 partitionConfig["var_ab_size"].toString().replace("G", "").toInt(),
                                 dualBoot, filesystemType, locale, timezone, keyboard, fullname, username, password, rootPassword
    );

    connect(m_worker, &InstallWorker::progressUpdated, this, &InstallationPage::updateProgress);
    connect(m_worker, &InstallWorker::finished, this, &InstallationPage::installationFinished);
    connect(m_worker, &InstallWorker::chrootEntered, this, &InstallationPage::onChrootEntered);

    connect(m_worker, &InstallWorker::chrootPromptDetected, this, [this]() {
        m_questionLabel->show();
        m_yesButton->show();
        m_noButton->show();
        m_inputField->hide();
        m_sendButton->hide();
        m_isYNPromptActive = true;
    });

    connect(m_worker, &InstallWorker::finished, [this]() {
        m_worker = nullptr;
    });

    m_worker->start();
}

void InstallationPage::sendInput()
{
    if (m_isYNPromptActive) {
        return;
    }

    QString text = m_inputField->text().trimmed();
    if (!text.isEmpty()) {
        m_logText->append(QString(">>> %1").arg(text));
        m_inputField->clear();

        if (m_worker) {
            m_worker->sendInput(text);
        }
    }
}

void InstallationPage::sendYN(const QString &choice)
{
    m_logText->append(QString(">>> %1").arg(choice));
    if (m_worker) {
        m_worker->sendInput(choice);
    }
    m_questionLabel->hide();
    m_yesButton->hide();
    m_noButton->hide();
    m_inputField->show();
    m_sendButton->show();
    m_isYNPromptActive = false;
    m_inputField->clear();
}

void InstallationPage::updateProgress(const QString &message)
{
    m_statusLabel->setText("Installation in progress...");
    if (message.contains("Do you want to chroot into slot 'a' to make changes before copying it to slot B? (y/N):")) {
        m_questionLabel->show();
        m_yesButton->show();
        m_noButton->show();
        m_inputField->hide();
        m_sendButton->hide();
        m_isYNPromptActive = true;
    }

    m_logText->append(message);
    QTextCursor cursor = m_logText->textCursor();
    cursor.movePosition(QTextCursor::End);
    m_logText->setTextCursor(cursor);
}

void InstallationPage::installationFinished(bool success, const QString &message)
{
    if (success) {
        m_statusLabel->setText("Installation completed successfully!");
        m_progressBar->setRange(0, 100);
        m_progressBar->setValue(100);
    } else {
        m_statusLabel->setText(QString("Installation failed: %1").arg(message));
        m_progressBar->setRange(0, 100);
        m_progressBar->setValue(0);
    }
    m_sendButton->setEnabled(false);
    m_inputField->setEnabled(false);
    emit installationComplete(success, message);
}

void InstallationPage::onChrootEntered()
{
    QMessageBox::StandardButton reply = QMessageBox::question(
        this, "Chroot", "You are now in chroot. Do you still want to be in chroot?",
        QMessageBox::Yes | QMessageBox::No, QMessageBox::Yes
    );
    if (reply == QMessageBox::No) {
    }
}

FinishedPage::FinishedPage(QWidget *parent)
    : QWidget(parent)
    , m_restartButton(nullptr)
    , m_showLogButton(nullptr)
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setAlignment(Qt::AlignCenter);
    layout->setSpacing(24);
    layout->setContentsMargins(60, 40, 60, 40);
    QLabel *iconLabel = new QLabel();
    iconLabel->setPixmap(QIcon::fromTheme("emblem-ok-symbolic").pixmap(96, 96));
    iconLabel->setAlignment(Qt::AlignCenter);
    QLabel *title = new QLabel("Installation Complete!");
    title->setObjectName("finished-title");
    title->setAlignment(Qt::AlignCenter);
    QLabel *message = new QLabel(
        "ObsidianOS has been successfully installed on your system.\n\n"
        "Please remove the installation media and restart your computer."
    );
    message->setObjectName("finished-message");
    message->setAlignment(Qt::AlignCenter);
    message->setWordWrap(true);
    ModernCard *card = new ModernCard();
    QVBoxLayout *cardLayout = new QVBoxLayout(card);
    cardLayout->setSpacing(16);
    cardLayout->setContentsMargins(32, 32, 32, 32);
    cardLayout->setAlignment(Qt::AlignCenter);
    cardLayout->addWidget(iconLabel);
    cardLayout->addWidget(title);
    cardLayout->addWidget(message);
    QHBoxLayout *buttonLayout = new QHBoxLayout();
    buttonLayout->setSpacing(16);
    m_showLogButton = new QPushButton("View Log");
    m_showLogButton->setObjectName("secondary-button");
    m_showLogButton->setIcon(QIcon::fromTheme("document-open"));
    connect(m_showLogButton, &QPushButton::clicked, this, &FinishedPage::showLog);
    m_restartButton = new QPushButton("Restart Now");
    m_restartButton->setObjectName("primary-button");
    m_restartButton->setIcon(QIcon::fromTheme("system-reboot"));
    connect(m_restartButton, &QPushButton::clicked, this, &FinishedPage::restartSystem);
    buttonLayout->addStretch();
    buttonLayout->addWidget(m_showLogButton);
    buttonLayout->addWidget(m_restartButton);
    buttonLayout->addStretch();
    cardLayout->addSpacing(16);
    cardLayout->addLayout(buttonLayout);
    layout->addStretch();
    layout->addWidget(card);
    layout->addStretch();
}

#include "Pages.moc"
