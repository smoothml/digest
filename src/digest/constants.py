from pathlib import Path
from string import Template

ROOT_DIR = Path(__file__).parent.parent.parent
POST_BASE_PATH_TEMPLATE = Template(f"{ROOT_DIR}/sites/$site/content")
