from sqlalchemy import Column, String, Integer

from models.base import Base

class Server(Base):
    __tablename__ = 'servers'

    id = Column(Integer, primary_key=True)
    discord_id = Column(String)
    name = Column(String)
    status = Column(Integer)
    channel = Column(String)
    min_role = Column(String)
    rx1 = Column(String)
    rx2 = Column(String)

    def __init__(self, discord_id, name, status, channel, min_role, rx1, rx2):
        self.discord_id = discord_id
        self.name = name
        self.status = status
        self.channel = channel
        self.min_role = min_role
        self.rx1 = rx1
        self.rx2 = rx2
