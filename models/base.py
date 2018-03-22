import json
import os.path

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

project_root = os.path.abspath(os.path.dirname(__file__))
file_path = os.path.join(project_root, '../config/db.json')

with open(file_path) as data_file:
    db_config = json.load(data_file)

engine = create_engine(db_config['database_uri'])
Session = sessionmaker(bind=engine)

Base = declarative_base()
