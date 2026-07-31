import logging

from src.database.connection import init_database
from src.workers import batch

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Running one-off batch download")
    init_database()
    batch.run_hk_batch()
    batch.run_us_batch()
    logger.info("Done")


if __name__ == "__main__":
    main()
