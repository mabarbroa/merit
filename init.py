"""
Blockscout Merit Bot Package

Automated bot for claiming daily merits on Blockscout using private key.
Bot automatically generates wallet address from private key.
"""

__version__ = "1.0.0"

# Import main bot class
try:
    from .merit_bot import GitHubActionsMeritBot
    __all__ = ['GitHubActionsMeritBot']
except ImportError:
    __all__ = []

# Package info
PACKAGE_INFO = {
    'name': 'blockscout-merit-bot',
    'version': __version__,
    'description': 'Automated Blockscout merit claiming bot with auto wallet address generation',
    'mode': 'private_key_based'
}
