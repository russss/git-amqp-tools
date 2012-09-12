# coding=utf-8
"""
Utility library for interacting with unimate
"""
import socket
import types


class Client(object):
    """
    Unimate client
    """
    def __init__(self, server, port):
        if not isinstance(server, types.StringTypes):
            raise TypeError("server must be a string")
        if not isinstance(port, (int, long)):
            raise TypeError("port must be an integer")
        self._server = server
        self._port = port

    def send(self, message, room=None):
        """Broadcast a message through unimate"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self._server, self._port))
        if isinstance(message, unicode):
            message = message.encode('utf-8')
        if room is None:
            msg = "broadcast %s\r\n" % message
        else:
            msg = "broadcast %s %s\r\n" % (room, message)
        sock.send(msg)
        sock.close()

