"""No test in this suite is allowed to open a network connection.

The judge is the only component that talks to a remote API, and it must always be stubbed.
This fixture makes a real connection attempt fail loudly rather than quietly costing money.
"""

import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("a test tried to open a network connection")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
