#include "Common.h"
bool isTestMode()
{
    static bool testMode = false;
    static bool initialized = false;
    if (!initialized) {
        testMode = QCoreApplication::arguments().contains("--test");
        initialized = true;
    }

    return testMode;
}
