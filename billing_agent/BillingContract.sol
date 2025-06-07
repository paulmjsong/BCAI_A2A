pragma solidity ^0.8.0;

contract PaymentContract {
    address public owner;
    uint256 public price;  // Set in wei
    mapping(address => uint256) public paidContent;

    event PaymentReceived(address indexed user, bytes32 indexed contentId, uint256 amount);

    constructor(uint256 _price) {
        owner = msg.sender;
        price = _price;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Not the contract owner");
        _;
    }

    // Function to pay for content
    function makePayment(bytes32 contentId) public onlyOwner {
        require(msg.value >= price, "Insufficient payment for content");
        require(!paidContent[contentId], "This content is already paid for");
        paidContent[contentId] = true;
        emit PaymentReceived(msg.sender, contentId, msg.value);
    }

    // Function to update price of content
    function updatePrice(uint _price) public onlyOwner {
        price = _price;
    }

    // Function to withdraw funds from contract
    function withdraw() public onlyOwner {
        payable(owner).transfer(address(this).balance);
    }
}
