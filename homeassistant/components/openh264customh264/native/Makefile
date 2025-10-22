# OpenH264 Shim Makefile
# Builds a shared library that wraps OpenH264's C++ API for Python ctypes

# Detect OpenH264 installation path
OPENH264_PREFIX ?= $(shell brew --prefix openh264 2>/dev/null || echo "/usr/local")
OPENH264_INCLUDE = $(OPENH264_PREFIX)/include
OPENH264_LIB = $(OPENH264_PREFIX)/lib

# Detect architecture and platform
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

ifeq ($(UNAME_S),Darwin)
    # macOS
    PLATFORM = macos
    DYLIB_EXT = dylib
    SHARED_FLAG = -shared
    EXTRA_FLAGS = -fPIC -arch $(UNAME_M)
    OPENH264_LINK = -lopenh264
else ifeq ($(UNAME_S),Linux)
    # Linux
    PLATFORM = linux
    DYLIB_EXT = so
    SHARED_FLAG = -shared
    EXTRA_FLAGS = -fPIC
    OPENH264_LINK = -lopenh264
else
    # Default/Windows
    PLATFORM = windows
    DYLIB_EXT = dll
    SHARED_FLAG = -shared
    EXTRA_FLAGS = 
    OPENH264_LINK = -lopenh264
endif

# Compiler settings
CC = clang
CXX = clang++
CFLAGS = -std=c11 -O2 -Wall -Wextra $(EXTRA_FLAGS)
CXXFLAGS = -std=c++11 -O2 -Wall -Wextra $(EXTRA_FLAGS)
INCLUDES = -I$(OPENH264_INCLUDE)
LDFLAGS = -L$(OPENH264_LIB) $(OPENH264_LINK)

# Output paths
OUTPUT_DIR = ../bin/$(PLATFORM)
OUTPUT_LIB = $(OUTPUT_DIR)/libopenh264shim.$(DYLIB_EXT)

# Source files
SOURCES = openh264_shim.c
HEADERS = openh264_shim.h

.PHONY: all clean check-deps install

all: check-deps $(OUTPUT_LIB)

check-deps:
	@echo "Checking dependencies..."
	@if [ ! -d "$(OPENH264_INCLUDE)" ]; then \
		echo "ERROR: OpenH264 headers not found at $(OPENH264_INCLUDE)"; \
		echo "Please install OpenH264: brew install openh264"; \
		exit 1; \
	fi
	@if [ ! -f "$(OPENH264_LIB)/libopenh264.$(DYLIB_EXT)" ]; then \
		echo "ERROR: OpenH264 library not found at $(OPENH264_LIB)"; \
		echo "Please install OpenH264: brew install openh264"; \
		exit 1; \
	fi
	@echo "Dependencies OK"

$(OUTPUT_DIR):
	mkdir -p $(OUTPUT_DIR)

$(OUTPUT_LIB): $(SOURCES) $(HEADERS) | $(OUTPUT_DIR)
	@echo "Building OpenH264 shim for $(PLATFORM)..."
	$(CXX) $(CXXFLAGS) $(SHARED_FLAG) $(INCLUDES) -o $@ $(SOURCES) $(LDFLAGS)
	@echo "Built: $@"
	@ls -l $@

clean:
	rm -rf ../bin

install: $(OUTPUT_LIB)
	@echo "Library built at: $(OUTPUT_LIB)"
	@echo "To test the library:"
	@echo "  otool -L $(OUTPUT_LIB)  # Check dependencies"
	@echo "  nm -D $(OUTPUT_LIB)     # Check exported symbols"

# Development targets
test-symbols: $(OUTPUT_LIB)
	@echo "Checking exported symbols..."
	nm -D $< | grep h264_encoder || nm $< | grep h264_encoder

test-deps: $(OUTPUT_LIB)
	@echo "Checking library dependencies..."
	otool -L $<

debug: CXXFLAGS += -g -DDEBUG
debug: $(OUTPUT_LIB)

# Help target
help:
	@echo "OpenH264 Shim Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all         - Build the shared library (default)"
	@echo "  clean       - Remove build artifacts"
	@echo "  check-deps  - Verify OpenH264 installation"
	@echo "  install     - Build and show usage info"
	@echo "  test-symbols- Check exported symbols"
	@echo "  test-deps   - Check library dependencies"
	@echo "  debug       - Build with debug symbols"
	@echo "  help        - Show this help"
	@echo ""
	@echo "Variables:"
	@echo "  OPENH264_PREFIX  - OpenH264 installation path (default: brew --prefix openh264)"
	@echo ""
	@echo "Current settings:"
	@echo "  Platform: $(PLATFORM)"
	@echo "  OpenH264: $(OPENH264_PREFIX)"
	@echo "  Output:   $(OUTPUT_LIB)"