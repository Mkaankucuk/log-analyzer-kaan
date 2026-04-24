import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


REQUIRED_PACKAGES = [
    "flask",
    "pandas",
    "psutil",
    "faker"
]


def install_packages():
    print("Gerekli paketler kontrol ediliyor ve yükleniyor...")

    for package in REQUIRED_PACKAGES:
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            package
        ])

    print("Paket kurulumu tamamlandı.")


def run_script(script_path):
    print(f"Çalıştırılıyor: {script_path.name}")

    subprocess.check_call([
        sys.executable,
        str(script_path)
    ])

    print(f"Tamamlandı: {script_path.name}")


def main():
    scripts_dir = BASE_DIR / "scripts"

    install_packages()

    run_script(scripts_dir / "generate_access_logs.py")
    run_script(scripts_dir / "generate_security_logs.py")

    run_script(BASE_DIR / "import_to_db.py")
    run_script(BASE_DIR / "import_security_to_db.py")

    print("Tüm kurulum ve veri hazırlama işlemleri tamamlandı.")
    print("Uygulamayı çalıştırmak için:")
    print("python run.py")


if __name__ == "__main__":
    main()