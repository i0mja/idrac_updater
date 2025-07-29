#!/usr/bin/env python3
"""Initialize iDRAC Updater database"""

from app import app, db
from models import Group

def initialize_database():
    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database tables created")
        
        # Create default groups
        if not Group.query.first():
            groups = [
                Group(name="Production", description="Production servers"),
                Group(name="Development", description="Development servers"),
                Group(name="Retired", description="Decommissioned servers"),
            ]
            db.session.add_all(groups)
            db.session.commit()
            print("Default groups created")

if __name__ == "__main__":
    initialize_database()
