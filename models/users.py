from sqlalchemy import Column, String, Integer, Date

from models.base import Base

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    discord_id = Column(String)
    user_name = Column(String)
    display_name = Column(String)

    def __init__(self, discord_id, user_name, display_name):
        self.discord_id = discord_id
        self.user_name = user_name
        self.display_name = display_name
