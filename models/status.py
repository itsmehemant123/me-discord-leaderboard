from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base
from models.servers import Server
from models.users import User

class Status(Base):
    __tablename__ = 'status'

    id = Column(Integer, primary_key=True)
    server_status = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    server_id = Column(Integer, ForeignKey('servers.id'), nullable=False)
    user = relationship(User)
    server = relationship(Server)


    def __init__(self, server_status, user, server):
        self.server_status = server_status
        self.user = user
        self.server = server
 
