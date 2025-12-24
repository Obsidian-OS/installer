DIST ?= /
all: clean build
run:
	build/ObsidianOSInstaller
test:
	build/ObsidianOSInstaller --test
clean:
	rm -rf build

build: clean
	mkdir -p build
	cd build && cmake ..
	cd build && make -j8

install:
	cp obsidianos-installer.desktop $(DIST)/usr/share/applications/
	cp build/ObsidianOSInstaller $(DIST)/usr/bin/
