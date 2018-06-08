from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base
from models.servers import Server
from models.users import User

class Nickname(Base):
    __tablename__ = 'nicknames'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    server_id = Column(Integer, ForeignKey('servers.id'), nullable=False)
    user = relationship(User)
    server = relationship(Server)
    display_name = Column(String)

    def __init__(self, user, server, display_name):
        self.user = user
        self.server = server
        self.display_name = display_name
