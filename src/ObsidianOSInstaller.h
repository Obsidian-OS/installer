#ifndef OBSIDIANOSINSTALLER_H
#define OBSIDIANOSINSTALLER_H
#include <QMainWindow>
#include <QStackedWidget>
#include <QPushButton>
#include <QWidget>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPixmap>
#include <QIcon>
#include <QDir>
#include <QMessageBox>
#include <QProcess>
#include <QDialog>
#include <QTextEdit>
#include <QFont>
#include "UIComponents.h"
#include "Pages.h"
class ObsidianOSInstaller : public QMainWindow
{
    Q_OBJECT

public:
    explicit ObsidianOSInstaller(QWidget *parent = nullptr);

private slots:
    void goBack();
    void goNext();
    void validateCurrentPage();
    void updateButtons();
    void updateSummary();
    void startInstallation();
    void installationFinished(bool success, const QString &message);
    void restartSystem();
    void showLog();

private:
    void initUI();
    void setupPages();
    int m_currentPage;
    QVector<QWidget*> m_pages;
    StepIndicator *m_stepIndicator;
    QStackedWidget *m_stackedWidget;
    QPushButton *m_backButton;
    QPushButton *m_nextButton;
    QPushButton *m_installButton;
};

#endif
