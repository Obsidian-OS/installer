DIST ?= /
all: clean build
run:
	build/ObsidianOSInstaller
test:
	build/ObsidianOSInstaller --test
clean:
	rm -rf build

build: clean
	mkdir build
	cd build && cmake ..
	cd build && make -j8

install: build
	cp obsidianos-installer.desktop $(DIST)/usr/share/applications/
	cp build/ObsidianOSInstaller $(DIST)/usr/bin/
