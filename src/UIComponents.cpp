#include "UIComponents.h"
ModernCard::ModernCard(QWidget *parent)
    : QFrame(parent)
{
    setObjectName("modern-card");
}

StepIndicator::StepIndicator(const QStringList &steps, QWidget *parent)
    : QWidget(parent)
    , m_steps(steps)
    , m_currentStep(0)
{
    setFixedHeight(60);
}

void StepIndicator::setCurrentStep(int step)
{
    m_currentStep = step;
    update();
}

void StepIndicator::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event)
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);
    QPalette palette = this->palette();
    QColor highlightColor = palette.highlight().color();
    QColor textColor = palette.text().color();
    QColor darkColor = palette.dark().color();
    QColor baseColor = palette.base().color();
    int totalWidth = width() - 80;
    int stepWidth = (m_steps.size() > 1) ? (totalWidth / (m_steps.size() - 1)) : totalWidth;
    int yCenter = height() / 2;
    for (int i = 0; i < m_steps.size() - 1; ++i) {
        int x1 = 40 + i * stepWidth;
        int x2 = 40 + (i + 1) * stepWidth;
        if (i < m_currentStep) {
            painter.setPen(highlightColor);
        } else {
            painter.setPen(darkColor);
        }
        painter.drawLine(x1, yCenter, x2, yCenter);
    }

    for (int i = 0; i < m_steps.size(); ++i) {
        int x = 40 + i * stepWidth;
        if (i < m_currentStep) {
            painter.setBrush(highlightColor);
            painter.setPen(highlightColor);
        } else if (i == m_currentStep) {
            painter.setBrush(highlightColor);
            painter.setPen(highlightColor);
        } else {
            painter.setBrush(baseColor);
            painter.setPen(darkColor);
        }
        painter.drawEllipse(x - 8, yCenter - 8, 16, 16);

        if (i == m_currentStep) {
            painter.setPen(textColor);
            QFont font = painter.font();
            font.setPointSize(8);
            painter.setFont(font);
            painter.drawText(x - 50, yCenter + 25, 100, 20, Qt::AlignCenter, m_steps[i]);
        }
    }
}

#include "UIComponents.moc"
