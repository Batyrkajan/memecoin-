import os
import time
import logging
from dotenv import load_dotenv
from web3 import Web3
from cryptography.fernet import Fernet
from solana.rpc.api import Client
from solana.keypair import Keypair
from solana.transaction import Transaction

# Step 1: Set up everything
# ---------------------------------------------

# Load environment variables
load_dotenv()


# Load encrypted private keys and decryption keys
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY").encode()
ENCRYPTED_PRIVATE_KEY = os.getenv("ENCRYPTED_PRIVATE_KEY")

# Load Phantom Wallet Private Key
PRIVATE_KEY_HEX = os.getenv("SOLANA_PRIVATE_KEY")

# Convert private key from hex to keypair
private_key_bytes = bytes.fromhex(PRIVATE_KEY_HEX)
wallet = Keypair.from_secret_key(private_key_bytes)

# Connect to Solana using RPC Provider
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL")  # Store this in .env
solana_client = Client(SOLANA_RPC_URL)


METAMUSK_ENCRYPTION_KEY = os.getenv("METAMUSK_ENCRYPTION_KEY").encode()
METAMUSK_ENCRYPTED_PRIVATE_KEY = os.getenv("METAMUSK_ENCRYPTED_PRIVATE_KEY")


# Decrypt private key
cipher_suite = Fernet(ENCRYPTION_KEY)
PRIVATE_KEY = cipher_suite.decrypt(ENCRYPTED_PRIVATE_KEY.encode()).decode()

cipher_suite_metamask = Fernet(METAMUSK_ENCRYPTION_KEY)
METAMASK_PRIVATE_KEY = cipher_suite_metamask.decrypt(METAMUSK_ENCRYPTED_PRIVATE_KEY.encode()).decode()


# Define blockchain providers
PROVIDERS = [
    os.getenv("INFURA_WS_URL"),
    os.getenv("ALCHEMY_WS_URL"),
    os.getenv("QUICKNODE_WS_URL")
]


# Setup logging
logging.basicConfig(
    filename='trading_bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Function to connect to blockchain
def connect_to_blockchain():
    for provider in PROVIDERS:
        try:
            w3 = Web3(Web3.WebsocketProvider(provider))
            if w3.is_connected():
                logging.info(f"Connected to Ethereum via {provider}")
                return w3
        except Exception as e:
            logging.error(f"Failed to connect using {provider}: {e}")

    logging.error("All providers failed! Retrying in 10 seconds...")
    time.sleep(10)
    return connect_to_blockchain()

# Connect to Ethereum
w3 = connect_to_blockchain()


# Load wallet
account = w3.eth.account.from_key(PRIVATE_KEY)
wallet_address = account.address

logging.info(f"Connected wallet: {wallet_address}")

# Step 2: Start With trading bot
# ---------------------------------------------------

def get_trending_coins():
    url = "https://api.dextools.io/trending-pairs"
    headers = {"Authorization": "Bearer YOUR_API_KEY"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        trending_coins = data['data']
        return trending_coins
    else:
        print("Error fetching trending coins")
        return []

trending_coins = get_trending_coins()
for coin in trending_coins:
    print(f"Token: {coin['symbol']} - Price: {coin['price']}")

    
ETHERSCAN_API = "YOUR_ETHERSCAN_API"

def track_whales(token_address):
    url = f"https://api.etherscan.io/api?module=account&action=txlist&address={token_address}&apikey={ETHERSCAN_API}"
    response = requests.get(url).json()

    for tx in response["result"]:
        if int(tx["value"]) > 10**18:  # Large transactions (>1 ETH)
            print(f"Whale bought: {tx['from']} - Amount: {int(tx['value'])/10**18} ETH")

track_whales("0xTokenAddressHere")

# Uniswap Router Contract
UNISWAP_ROUTER = "0x7a250d5630b4cf539739df2c5dacb4c659f2488d"

def buy_token(token_address, eth_amount):
    contract = w3.eth.contract(address=UNISWAP_ROUTER, abi=uniswap_abi)
    
    txn = contract.functions.swapExactETHForTokens(
        0,  # Min tokens (set to 0 for simplicity)
        [w3.to_checksum_address(WETH_ADDRESS), w3.to_checksum_address(token_address)],  
        wallet_address,  
        int(w3.eth.get_block('latest')['timestamp']) + 1200  # Expiration time
    ).build_transaction({
        'from': wallet_address,
        'value': w3.to_wei(eth_amount, 'ether'),
        'gas': 2000000,
        'gasPrice': w3.to_wei('5', 'gwei'),
        'nonce': w3.eth.get_transaction_count(wallet_address),
    })

    signed_txn = w3.eth.account.sign_transaction(txn, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    print(f"Transaction sent! TX Hash: {tx_hash.hex()}")

buy_token("0xTokenAddressHere", 0.1)

def sell_token(token_address, token_amount):
    contract = w3.eth.contract(address=UNISWAP_ROUTER, abi=uniswap_abi)
    
    txn = contract.functions.swapExactTokensForETH(
        token_amount,
        0,  
        [w3.to_checksum_address(token_address), w3.to_checksum_address(WETH_ADDRESS)],  
        wallet_address,  
        int(w3.eth.get_block('latest')['timestamp']) + 1200  
    ).build_transaction({
        'from': wallet_address,
        'gas': 2000000,
        'gasPrice': w3.to_wei('5', 'gwei'),
        'nonce': w3.eth.get_transaction_count(wallet_address),
    })

    signed_txn = w3.eth.account.sign_transaction(txn, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    print(f"Token sold! TX Hash: {tx_hash.hex()}")

sell_token("0xTokenAddressHere", 1000)

def get_token_price(token_address):
    url = f"https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses={token_address}&vs_currencies=usd"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        price = data[token_address.lower()]["usd"]
        return price
    else:
        print("Error fetching price data")
        return None

# Example usage
token_address = "0xTokenAddressHere"
current_price = get_token_price(token_address)
print(f"Current Price: ${current_price}")

# Define entry price & stop-loss/take-profit levels
ENTRY_PRICE = 0.01  # Example entry price
STOP_LOSS = ENTRY_PRICE * 0.8  # -20% Stop-Loss
TAKE_PROFIT = ENTRY_PRICE * 2  # +100% Take-Profit

def trade_monitor(token_address):
    while True:
        current_price = get_token_price(token_address)

        if current_price:
            print(f"Current Price: ${current_price}")

            if current_price <= STOP_LOSS:
                print("Stop-Loss hit! Selling...")
                sell_token(token_address, 1000)
                break

            if current_price >= TAKE_PROFIT:
                print("Take-Profit hit! Selling...")
                sell_token(token_address, 1000)
                break

        time.sleep(10)  # Check price every 10 seconds

# Run the monitor
trade_monitor("0xTokenAddressHere")

TRAILING_STOP_PERCENT = 0.15  # Stop-loss follows 15% below peak price

def trailing_stop_loss(token_address):
    peak_price = ENTRY_PRICE  # Start with entry price
    stop_loss = ENTRY_PRICE * (1 - TRAILING_STOP_PERCENT)

    while True:
        current_price = get_token_price(token_address)

        if current_price:
            print(f"Current Price: ${current_price}, Peak Price: ${peak_price}, Stop-Loss: ${stop_loss}")

            if current_price > peak_price:
                peak_price = current_price  # Update peak price
                stop_loss = peak_price * (1 - TRAILING_STOP_PERCENT)  # Move stop-loss up

            if current_price <= stop_loss:
                print("Trailing Stop-Loss hit! Selling...")
                sell_token(token_address, 1000)
                break

        time.sleep(10)  # Check price every 10 seconds

# Run the trailing stop-loss
trailing_stop_loss("0xTokenAddressHere")

FAST_GAS_PRICE = w3.to_wei('15', 'gwei')  # Increase gas price for speed

def buy_token_fast(token_address, eth_amount):
    contract = w3.eth.contract(address=UNISWAP_ROUTER, abi=uniswap_abi)

    txn = contract.functions.swapExactETHForTokens(
        0,  
        [w3.to_checksum_address(WETH_ADDRESS), w3.to_checksum_address(token_address)],  
        wallet_address,  
        int(w3.eth.get_block('latest')['timestamp']) + 1200  
    ).build_transaction({
        'from': wallet_address,
        'value': w3.to_wei(eth_amount, 'ether'),
        'gas': 300000,  # Increase gas limit
        'gasPrice': FAST_GAS_PRICE,  # Use fast gas price
        'nonce': w3.eth.get_transaction_count(wallet_address),
    })

    signed_txn = w3.eth.account.sign_transaction(txn, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    print(f"Transaction sent with higher gas! TX Hash: {tx_hash.hex()}")
