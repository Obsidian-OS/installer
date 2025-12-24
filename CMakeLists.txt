cmake_minimum_required(VERSION 3.16)
project(ObsidianOSInstaller VERSION 1.0.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
find_package(Qt6 REQUIRED COMPONENTS Core Widgets)
qt_standard_project_setup()
set(SOURCES
    src/Common.cpp
    src/main.cpp
    src/InstallWorker.cpp
    src/UIComponents.cpp
    src/Pages.cpp
    src/ObsidianOSInstaller.cpp
)

set(HEADERS
    src/Common.h
    src/InstallWorker.h
    src/UIComponents.h
    src/Pages.h
    src/ObsidianOSInstaller.h
)

qt_add_executable(ObsidianOSInstaller ${SOURCES} ${HEADERS})
qt_add_resources(ObsidianOSInstaller "resources"
    PREFIX "/"
    FILES
        logo.svg
)

target_link_libraries(ObsidianOSInstaller PRIVATE Qt6::Core Qt6::Widgets)
install(TARGETS ObsidianOSInstaller
    RUNTIME DESTINATION bin
)
