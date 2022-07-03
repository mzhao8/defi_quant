from brownie import accounts, config, interface, network
from web3 import Web3
from scripts.get_weth import get_weth

amount = Web3.toWei(0.1, "ether")


def main():
    account = get_account()
    erc20_address = config["networks"][network.show_active()]["weth_token"]
    if network.show_active() in ["mainnet-fork"]:
        get_weth(account=account)

    # get the lending pool address through the lending pool address provider - see below - a "read" function
    lending_pool = get_lending_pool()

    # approve 1. token 2. amount 3. lending pool address 4. from your account - a "write" function
    approve_erc20(amount, lending_pool.address, erc20_address, account)
    print("Depositing...")

    # call the deposit function from the lending pool contract - a "write" function
    lending_pool.deposit(erc20_address, amount, account.address, 0, {"from": account})
    print("Deposited!")

    # after deposit, calls a "read" function
    borrowable_eth, total_debt_eth = get_borrowable_data(lending_pool, account)
    print(f"LETS BORROW IT ALL")

    # get prices - a "read" function
    erc20_eth_price = get_asset_price()

    # calculate 95% of our borrow
    amount_erc20_to_borrow = (1 / erc20_eth_price) * (borrowable_eth * 0.95)
    print(f"We are going to borrow {amount_erc20_to_borrow} DAI")

    # borrow against the smart contract - "write" function
    borrow_erc20(lending_pool, amount_erc20_to_borrow, account)

    # "read" function
    borrowable_eth, total_debt_eth = get_borrowable_data(lending_pool, account)

    # amount_erc20_to_repay = (1 / erc20_eth_price) * (total_debt_eth * 0.95)
    repay_all(amount_erc20_to_borrow, lending_pool, account)

    # Then print out our borrowable data
    get_borrowable_data(lending_pool, account)


def get_account():
    if network.show_active() in ["hardhat", "development", "mainnet-fork"]:
        return accounts[0]
    if network.show_active() in config["networks"]:
        account = accounts.add(config["wallets"]["from_key"])
        return account
    return None


""" 
get_lending_pool()

since lending pool addresses change, we get the address from the lending pool addresses provider, a smart contract that directs us to the correct address

calls this following function from https://github.com/aave/aave-protocol/blob/master/contracts/lendingpool/LendingPool.sol: 

    function getLendingPool() public view returns (address) {
        return getAddress(LENDING_POOL);
    }

which calls getAddress from this https://github.com/aave/aave-protocol/blob/master/contracts/configuration/AddressStorage.sol:
    
    mapping(bytes32 => address) private addresses;

    function getAddress(bytes32 _key) public view returns (address) {
        return addresses[_key];
    }

returns a contract as a python class.

"""


def get_lending_pool():
    lending_pool_addresses_provider = interface.ILendingPoolAddressesProvider(
        config["networks"][network.show_active()]["lending_pool_addresses_provider"]
    )
    lending_pool_address = lending_pool_addresses_provider.getLendingPool()
    lending_pool = interface.ILendingPool(lending_pool_address)
    return lending_pool


"""
approve_erc20()

approve amount to deposit onto the lending pool smart contract.

common steps for write contracts: 
1. create variable that is basically the interface.[solidity contract name](address)
2. the variable is smart contract that basically is a class
    
    for example: erc20 = interface.IERC20(erc20_address)
    erc20 basically is a smart contract class, can call the smart contract functions


"""


def approve_erc20(amount, lending_pool_address, erc20_address, account):
    print("Approving ERC20...")
    erc20 = interface.IERC20(erc20_address)
    tx_hash = erc20.approve(lending_pool_address, amount, {"from": account})
    tx_hash.wait(1)
    print("Approved!")
    return True


"""
get_borrowable_data

calls "read function" getUserAccountData from the lending pool contract, which returns:
    totalCollateralETH uint256, 
    totalDebtETH uint256, 
    availableBorrowsETH uint256, 
    currentLiquidationThreshold uint256, 
    ltv uint256, 
    healthFactor uint256

"""


def get_borrowable_data(lending_pool, account):
    (
        total_collateral_eth,
        total_debt_eth,
        available_borrow_eth,
        current_liquidation_threshold,
        tlv,
        health_factor,
    ) = lending_pool.getUserAccountData(account.address)
    available_borrow_eth = Web3.fromWei(available_borrow_eth, "ether")
    total_collateral_eth = Web3.fromWei(total_collateral_eth, "ether")
    total_debt_eth = Web3.fromWei(total_debt_eth, "ether")
    print(f"You have {total_collateral_eth} worth of ETH deposited.")
    print(f"You have {total_debt_eth} worth of ETH borrowed.")
    print(f"You can borrow {available_borrow_eth} worth of ETH.")
    return (float(available_borrow_eth), float(total_debt_eth))


"""
borrow_erc20()

important piece here is the lending_pool.borrow() call

"""


def borrow_erc20(lending_pool, amount, account, erc20_address=None):
    erc20_address = (
        erc20_address
        if erc20_address
        else config["networks"][network.show_active()]["aave_dai_token"]
    )
    # 1 is stable interest rate
    # 0 is the referral code
    transaction = lending_pool.borrow(
        erc20_address,
        Web3.toWei(amount, "ether"),
        1,
        0,
        account.address,
        {"from": account},
    )
    transaction.wait(1)
    print(f"Congratulations! We have just borrowed {amount}")


def get_asset_price():
    # For mainnet we can just do:
    # return Contract(f"{pair}.data.eth").latestAnswer() / 1e8
    dai_eth_price_feed = interface.AggregatorV3Interface(
        config["networks"][network.show_active()]["dai_eth_price_feed"]
    )
    latest_price = Web3.fromWei(dai_eth_price_feed.latestRoundData()[1], "ether")
    print(f"The DAI/ETH price is {latest_price}")
    return float(latest_price)


def repay_all(amount, lending_pool, account):
    approve_erc20(
        Web3.toWei(amount, "ether"),
        lending_pool,
        config["networks"][network.show_active()]["aave_dai_token"],
        account,
    )
    tx = lending_pool.repay(
        config["networks"][network.show_active()]["aave_dai_token"],
        Web3.toWei(amount, "ether"),
        1,
        account.address,
        {"from": account},
    )
    tx.wait(1)
    print("Repaid!")


if __name__ == "__main__":
    main()
