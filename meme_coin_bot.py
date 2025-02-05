import os
import logging
import time
from dotenv import load_dotenv
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.transaction import Transaction
from base58 import b58decode
import requests

# Step 1: Load Private Keys & Connect to Blockchain
# --------------------------------

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    filename="trading_bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Load and decrypt Solana private key
SOLANA_PRIVATE_KEY_B58 = os.getenv("SOLANA_PRIVATE_KEY")
private_key_bytes = b58decode(SOLANA_PRIVATE_KEY_B58)
wallet = Keypair.from_bytes(private_key_bytes)

# Connect to Solana RPC
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL")
solana_client = Client(SOLANA_RPC_URL)

logging.info("Connected to Solana RPC")
print("✅ Connected to Solana")


# Step 2: Real-Time Price Monitoring
# --------------------------------


def get_token_price(token_mint):
    """Fetch token price from Jupiter API"""
    url = f"https://quote-api.jup.ag/v4/price?ids={token_mint}"
    response = requests.get(url)
    
    if response.status_code == 200:
        try:
            data = response.json()
            print("Raw response JSON:", data)  # Debug print to inspect the response structure
            # Use .get() to safely extract nested values
            price = data.get("data", {}).get(token_mint, {}).get("price")
            return price
        except Exception as e:
            logging.error(f"Error parsing price data: {e}")
            return None
    else:
        logging.error(f"Error fetching price data, status code: {response.status_code}")
        return None


# Example usage
TOKEN_MINT = "EPjFWdd5AufqSSqeM2q9GJwXxnR5vGZHyjC4oMQi3uN"  # Example SOL token
price = get_token_price(TOKEN_MINT)

print(f"Current Price: {get_token_price(price)} SOL")

# Step 3: Implement Buy on Dip Logic
# --------------------------------


def buy_token(token_mint, amount_sol):
    """Buy token using Jupiter Aggregator"""
    url = "https://quote-api.jup.ag/v4/swap"
    params = {
        "inputMint": "So11111111111111111111111111111111111111112",  # SOL token
        "outputMint": token_mint,
        "amount": int(amount_sol * (10**9)),  # Convert SOL to base units
        "slippageBps": 50,  # 0.5% slippage tolerance
        "userPublicKey": wallet.pubkey().__str__(),
    }
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        swap_data = response.json()
        print(f"✅ Buy Order Placed: {swap_data['outAmount']} {token_mint}")
        return swap_data
    else:
        logging.error("❌ Buy Order Failed:", response.json())
        return None

# Example Usage: Buy 0.1 SOL worth of Token
BUY_PRICE = 0.05  # Example buy price (if it drops to 0.05 SOL)
if price and price <= BUY_PRICE:
    buy_token(TOKEN_MINT, 0.1)

# Step 4: Implement Sell on Profit Logic
# --------------------------------

def sell_token(token_mint, amount_tokens):
    """Sell token using Jupiter Aggregator"""
    url = "https://quote-api.jup.ag/v4/swap"
    params = {
        "inputMint": token_mint,
        "outputMint": "So11111111111111111111111111111111111111112",  # Sell back to SOL
        "amount": int(amount_tokens * (10**9)),  # Convert to base units
        "slippageBps": 50,  # 0.5% slippage
        "userPublicKey": wallet.pubkey().__str__(),
    }
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        swap_data = response.json()
        print(f"✅ Sell Order Placed: {swap_data['outAmount']} SOL")
        return swap_data
    else:
        logging.error("❌ Sell Order Failed:", response.json())
        return None

# Example Usage: Sell for Profit
SELL_PRICE = 0.06  # Example sell price (profit target)
if price and price >= SELL_PRICE:
    sell_token(TOKEN_MINT, 10)  # Example amount

# Step 5: Implement Automated Trading Strategy

ENTRY_PRICE = None  # Store price at which we buy
PROFIT_TARGET = 1.2  # Sell when price is 20% above buy price

def trading_bot(token_mint, buy_price, sol_amount):
    """Continuously monitor and trade token"""
    global ENTRY_PRICE
    while True:
        current_price = get_token_price(token_mint)

        if current_price:
            print(f"Current Price: {current_price} SOL")

            # Buy when price dips
            if ENTRY_PRICE is None and current_price <= buy_price:
                print("📉 Price dropped! Buying...")
                buy_order = buy_token(token_mint, sol_amount)
                if buy_order:
                    ENTRY_PRICE = current_price  # Store entry price

            # Sell when profit target is reached
            elif ENTRY_PRICE and current_price >= ENTRY_PRICE * PROFIT_TARGET:
                print("💰 Profit Target Reached! Selling...")
                sell_order = sell_token(token_mint, 10)  # Example sell amount
                if sell_order:
                    ENTRY_PRICE = None  # Reset entry price

        time.sleep(1)  # Check price every second

# Run trading bot
trading_bot(TOKEN_MINT, BUY_PRICE, 0.1)
