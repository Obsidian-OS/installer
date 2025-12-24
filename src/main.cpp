#include <QApplication>
#include <QDir>
#include <QStyleFactory>
#include "ObsidianOSInstaller.h"
#include "Common.h"

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    app.setApplicationName("ObsidianOS Installer");
    app.setApplicationVersion("1.0.0");
    app.setOrganizationName("ObsidianOS");
    QString css = R"(
    QLabel#page-header {
        font-size: 18pt;
        font-weight: bold;
        padding-bottom: 4px;
    }

    QLabel#page-description {
        font-size: 10pt;
        padding-bottom: 8px;
    }

    QLabel#section-title {
        font-size: 11pt;
        font-weight: bold;
        color: palette(highlight);
        padding-top: 8px;
        padding-bottom: 4px;
    }

    QLabel#feature-title {
        font-size: 11pt;
        font-weight: bold;
        padding-bottom: 2px;
    }

    QLabel#feature-desc {
        font-size: 9pt;
        color: palette(text);
    }

    QLabel#welcome-title {
        font-size: 24pt;
        font-weight: bold;
        padding-bottom: 8px;
    }

    QLabel#welcome-subtitle {
        font-size: 12pt;
        color: palette(text);
        padding-bottom: 16px;
    }

    QLabel#finished-title {
        font-size: 20pt;
        font-weight: bold;
        padding-bottom: 8px;
    }

    QLabel#finished-message {
        font-size: 11pt;
        color: palette(text);
        padding-bottom: 16px;
    }

    QLabel#status-label {
        font-size: 12pt;
        font-weight: bold;
    }

    QLabel#summary-label {
        font-weight: bold;
        padding-right: 12px;
    }

    QLabel#summary-value {
        color: palette(text);
        word-wrap: true;
    }

    QLabel#question-label {
        font-weight: bold;
        padding: 4px 0;
    }

    QLabel#warning-text {
        color: #e67e22;
        font-weight: bold;
    }

    QLabel#info-text {
        color: #3498db;
    }

    QLabel#option-desc {
        color: palette(text);
        font-size: 9pt;
    }
    )";

    app.setStyleSheet(css);

    ObsidianOSInstaller installer;
    installer.show();

    return app.exec();
}
