#ifndef UICOMPONENTS_H
#define UICOMPONENTS_H
#include <QWidget>
#include <QFrame>
#include <QLabel>
#include <QPainter>
#include <QPaintEvent>
#include <QStringList>
class ModernCard : public QFrame
{
    Q_OBJECT

public:
    explicit ModernCard(QWidget *parent = nullptr);
};

class StepIndicator : public QWidget
{
    Q_OBJECT

public:
    explicit StepIndicator(const QStringList &steps, QWidget *parent = nullptr);
    void setCurrentStep(int step);

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    QStringList m_steps;
    int m_currentStep;
};

#endif
