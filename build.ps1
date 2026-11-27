# Creates the portable, no-console Windows executable in .\dist.
# The EXE needs no installer: its first launch can enable Start with Windows.
$ErrorActionPreference = 'Stop'
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Speedometer speedometer.py
Write-Host "Built portable EXE: $PWD\dist\Speedometer.exe"
