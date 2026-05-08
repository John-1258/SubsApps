import psutil
import platform

def get_total_ram_gb() -> float:
    return psutil.virtual_memory().total / (1024**3)

def recommend_whisper_model() -> str:
    ram = get_total_ram_gb()
    sys = platform.system().lower()

    # Conservative defaults (CPU-only assumptions)
    if ram < 6:
        return "base"
    if ram < 10:
        return "small"
    if ram < 16:
        return "medium"
    return "medium"  # keep medium as max for most laptops
