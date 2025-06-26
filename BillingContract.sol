// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract PaymentContract {
    address public owner;
    uint256 public price;  // Price per content in wei
    
    /// Mapping: buyer address => contentId => hasPaid
    mapping(address => mapping(bytes32 => bool)) public paidContent;

    event PaymentReceived(address indexed user, bytes32 indexed contentId, uint256 amount);

    constructor(uint256 _price) {
        owner = msg.sender;
        price = _price;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Not the contract owner");
        _;
    }

    /// @notice Buyer makes payment for access to specific content
    function makePayment(bytes32 contentId) external payable {
        require(msg.value >= price, "Insufficient payment for content");
        require(!(paidContent[msg.sender][contentId]), "This content is already paid for");

        paidContent[msg.sender][contentId] = true;
        emit PaymentReceived(msg.sender, contentId, msg.value);
    }

    /// @notice Verify whether a user has paid for a specific content
    function hasPaid(address user, bytes32 contentId) external view returns (bool) {
        return paidContent[user][contentId];
    }

    /// @notice Update global price
    function updatePrice(uint _price) public onlyOwner {
        price = _price;
    }

    /// @notice Withdraw contract balance to owner
    function withdraw() public onlyOwner {
        payable(owner).transfer(address(this).balance);
    }

    /// @notice Reject accidental ETH transfers
    receive() external payable {
        revert("Use makePayment function");
    }

    fallback() external payable {
        revert("Invalid call");
    }
}