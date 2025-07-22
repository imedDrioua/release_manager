"""Setup script for initializing the database"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from database.db_manager import DatabaseManager
from config.settings import get_current_release, get_release_dates

def setup_database():
    """Initialize database with sample data"""
    print("🗄️  Setting up database...")

    db_manager = DatabaseManager()

    # Create sample releases
    releases = ["week2025.30", "week2025.29", "week2025.28"]

    for release_id in releases:
        release_dates = get_release_dates(release_id)
        success = db_manager.create_release(
            release_id,
            release_dates['start_date'],
            release_dates['end_date']
        )
        if success:
            print(f"✅ Created release: {release_id}")
        else:
            print(f"⚠️  Release {release_id} already exists")

    print("✅ Database setup complete!")

if __name__ == "__main__":
    setup_database()
