// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AgentEscrow
 * @author  …
 *
 * A lightweight escrow that matches the updated A2A-based business flow:
 *
 *    1. Seller --> initiatePayment(buyer, amount, orderId)  (locks funds)
 *    2. Buyer confirms off-chain
 *    3. Seller --> settlePayment(orderId)                    (releases funds)
 *    4. If Buyer complains -> Seller --> refund(orderId)     (returns funds)
 *
 * - Each order is identified by a user-supplied `bytes32 orderId`
 * - Ether is the settlement asset; switch to ERC-20 with IERC20 if needed.
 * - Only the Seller that funded an order can settle / refund it.
 */

contract AgentEscrow {
    /* ---------- parameters ---------- */
    uint256 public constant BUYER_REFUND_TIMEOUT = 1 days;

    /* ---------- data types ---------- */
    enum Status { None, Created, Funded, Confirmed, Disputed, Settled, Refunded }

    struct Order {
        address buyer;
        address seller;
        uint96  amount;
        uint64  paidAt;        // timestamp when buyer funded
        Status  status;
    }

    mapping(bytes32 => Order) public orders;

    /* ---------- errors ---------- */
    error OrderExists();
    error UnknownOrder();
    error NotSeller();
    error NotBuyer();
    error WrongStatus();
    error AmountMismatch();
    error TooEarly();
    error TransferFailed();

    /* ---------- events ---------- */
    event OrderCreated   (bytes32 indexed id, address indexed seller, address indexed buyer, uint256 amount);
    event PaymentLocked  (bytes32 indexed id, address buyer, uint256 amount);
    event OrderConfirmed (bytes32 indexed id);
    event OrderDisputed  (bytes32 indexed id);
    event PaymentSettled (bytes32 indexed id, address seller, uint256 amount);
    event PaymentRefunded(bytes32 indexed id, address buyer,  uint256 amount);

    /* ---------- re-entrancy guard ---------- */
    uint256 private _locked = 1;
    modifier nonReentrant() {
        require(_locked == 1, "Re-entrancy");
        _locked = 2;
        _;
        _locked = 1;
    }

    /* -------------------------------- */
    /*            public API            */
    /* -------------------------------- */

    /// **Step 0** - Seller defines an order the buyer can pay into
    function createOrder(
        bytes32 orderId,
        address buyer,
        uint256 amountWei
    ) external {
        if (orders[orderId].status != Status.None) revert OrderExists();

        orders[orderId] = Order({
            buyer:   buyer,
            seller:  msg.sender,
            amount:  uint96(amountWei),
            paidAt:  0,
            status:  Status.Created
        });
        emit OrderCreated(orderId, msg.sender, buyer, amountWei);
    }

    /// **Step 1** - Buyer funds the order
    function makePayment(bytes32 orderId) external payable nonReentrant {
        Order storage o = _load(orderId);
        if (o.status != Status.Created)     revert WrongStatus();
        if (msg.sender != o.buyer)          revert NotBuyer();
        if (msg.value  != o.amount)         revert AmountMismatch();

        o.status = Status.Funded;
        o.paidAt = uint64(block.timestamp);
        emit PaymentLocked(orderId, msg.sender, msg.value);
    }

    /// **Step 4-5** - Buyer is satisfied
    function confirmOrder(bytes32 orderId) external {
        Order storage o = _load(orderId);
        if (o.status != Status.Funded)      revert WrongStatus();
        if (msg.sender != o.buyer)          revert NotBuyer();
        o.status = Status.Confirmed;
        emit OrderConfirmed(orderId);
    }

    /// **Step 7** - Buyer unhappy → open on-chain dispute
    function raiseDispute(bytes32 orderId) external {
        Order storage o = _load(orderId);
        if (o.status != Status.Funded)      revert WrongStatus();
        if (msg.sender != o.buyer)          revert NotBuyer();
        o.status = Status.Disputed;
        emit OrderDisputed(orderId);
    }

    /// **Step 6** - Seller gets paid only from Confirmed
    function settlePayment(bytes32 orderId) external nonReentrant {
        Order storage o = _load(orderId);
        if (msg.sender != o.seller)         revert NotSeller();
        if (o.status != Status.Confirmed)   revert WrongStatus();

        o.status = Status.Settled;
        _payout(o.seller, o.amount);
        emit PaymentSettled(orderId, o.seller, o.amount);
    }

    /// **Step 8** - Seller refunds after dispute
    function refund(bytes32 orderId) external nonReentrant {
        Order storage o = _load(orderId);
        if (msg.sender != o.seller)         revert NotSeller();
        if (o.status != Status.Disputed)    revert WrongStatus();

        o.status = Status.Refunded;
        _payout(o.buyer, o.amount);
        emit PaymentRefunded(orderId, o.buyer, o.amount);
    }

    /// **Step 9** - Buyer forces refund if seller silent too long
    function buyerTimeoutRefund(bytes32 orderId) external nonReentrant {
        Order storage o = _load(orderId);
        if (o.status != Status.Disputed)            revert WrongStatus();
        if (block.timestamp < o.paidAt + BUYER_REFUND_TIMEOUT) revert TooEarly();

        // anybody can call—protects buyer if their wallet is offline
        o.status = Status.Refunded;
        _payout(o.buyer, o.amount);
        emit PaymentRefunded(orderId, o.buyer, o.amount);
    }

    /* ------------------------------ */
    /*            internal            */
    /* ------------------------------ */
    
    function _load(bytes32 id) internal view returns (Order storage o) {
        o = orders[id];
        if (o.status == Status.None) revert UnknownOrder();
    }

    function _payout(address to, uint256 value) internal {
        (bool ok, ) = to.call{value: value}("");
        if (!ok) revert TransferFailed();
    }

    /* block stray ETH */
    receive() external payable { revert("pay via makePayment"); }
    fallback() external payable { revert(); }
}