pragma solidity ^0.8.0;

contract ResearchContentBilling {
    address public owner;
    uint256 public pricePerContent;  // Set in wei

    mapping(address => uint256) public userBalances;

    event ContentPurchased(address indexed user, uint256 amountPaid);

    constructor(uint256 _pricePerContent) {
        owner = msg.sender;
        pricePerContent = _pricePerContent;
    }

    // Function to purchase content
    function purchaseContent() external payable {
        require(msg.value >= pricePerContent, "Insufficient funds to purchase content");
        
        uint256 refund = msg.value - pricePerContent;
        if (refund > 0) {
            payable(msg.sender).transfer(refund); // Refund excess payment
        }

        userBalances[msg.sender] += pricePerContent;

        emit ContentPurchased(msg.sender, pricePerContent);
    }

    // Function to withdraw funds by the owner
    function withdraw() external {
        require(msg.sender == owner, "Only the owner can withdraw funds");
        payable(owner).transfer(address(this).balance);
    }

    // Function to update content price
    function setContentPrice(uint256 newPrice) external {
        require(msg.sender == owner, "Only the owner can set the price");
        pricePerContent = newPrice;
    }
}