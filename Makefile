.PHONY: build install clean uninstall

BINARY_NAME=smart-ffmpeg
SCRIPT_NAME=smart_ffmpeg.py

build:
	@echo "Building $(BINARY_NAME)..."
	uv run pyinstaller --onefile --name $(BINARY_NAME) --clean $(SCRIPT_NAME)
	@echo "Build complete. Binary is in dist/$(BINARY_NAME)"

install: build
	@echo "Installing to /usr/local/bin (requires sudo)..."
	sudo cp dist/$(BINARY_NAME) /usr/local/bin/$(BINARY_NAME)
	@echo "Installation complete. You can now run '$(BINARY_NAME)' from anywhere."

uninstall:
	@echo "Removing $(BINARY_NAME) from /usr/local/bin (requires sudo)..."
	sudo rm -f /usr/local/bin/$(BINARY_NAME)
	@echo "Uninstalled."

clean:
	@echo "Cleaning up build artifacts..."
	rm -rf build dist *.spec __pycache__
	@echo "Clean complete."
