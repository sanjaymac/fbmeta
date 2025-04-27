# install_playwright.py
import subprocess

def install_playwright():
    """Install Playwright browsers."""
    subprocess.run(["playwright", "install"], check=True)

if __name__ == "__main__":
    install_playwright()
