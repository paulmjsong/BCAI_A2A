pragma solidity ^0.8.0;

contract ContentBilling {
    address public owner;
    uint256 public price;  // Set in wei
    mapping(address => uint256) public paidContent;

    event PaymentReceived(address indexed user, bytes32 indexed contentId, uint256 amount);

    constructor(uint256 _price) {
        owner = msg.sender;
        price = _price;
    }

    // Function to pay for content
    function payForContent(bytes32 contentId) external payable {
        require(msg.value >= price, "Insufficient payment for content");
        require(!paidContent[contentId], "This content is already paid for");
        paidContent[contentId] = true;
        emit PaymentReceived(msg.sender, contentId, msg.value);
    }

    // Function to withdraw funds from contract
    function withdraw() external {
        require(msg.sender == owner, "Only owner can withdraw");
        payable(owner).transfer(address(this).balance);
    }

    // Function to reject direct transfers (must call payForContent to attach ID)
    receive() external payable {
        revert("Please use payForContent to pay");
    }
}
