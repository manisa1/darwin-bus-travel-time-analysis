from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "data"
DARWIN_BUS_TRAVEL_DATA_DIR = DATASET_DIR / "darwin_bus_travel_time_dataset"
OUTPUT_DIR = BASE_DIR / "outputs"
DARWIN_CBD = (-12.464786, 130.844340)

OUTPUT_DIR.mkdir(exist_ok=True)