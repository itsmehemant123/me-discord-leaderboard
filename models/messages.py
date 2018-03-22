from sqlalchemy import Column, String, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base
from models.servers import Server
from models.users import User

class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    discord_id = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'))
    server_id = Column(Integer, ForeignKey('servers.id'))
    user = relationship(User)
    server = relationship(Server)
    content = Column(String)
    created_at = Column(Date)
    rx1_count = Column(Integer)
    rx2_count = Column(Integer)
    
    def __init__(self, discord_id, server, author, content, created_at, rx1_count, rx2_count):
        self.discord_id = discord_id
        self.server = server
        self.author = author
        self.content = content
        self.created_at = created_at
        self.rx1_count = rx1_count
        self.rx2_count = rx2_count
