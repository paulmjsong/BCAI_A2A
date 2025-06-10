// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract PaymentContract {
    address public owner;
    uint256 public price;  // Set in wei
    // "어떤 주소가 특정 콘텐츠를 결제했는가"를 기록
    mapping(address => mapping(bytes32 => bool)) public paidContent; // user => (contentId => paid?)

    event PaymentReceived(address indexed user, bytes32 indexed contentId, uint256 amount);

    // 배포자가 자동으로 owner가 되고, price가 초기화됨
    constructor(uint256 _price) {
        owner = msg.sender;
        price = _price;
    }

    // owner만 호출할 수 있게 설정
    modifier onlyOwner() {
        require(msg.sender == owner, "Not the contract owner");
        _;
    }

    // Function to pay for content
    function makePayment(bytes32 contentId) external payable{
        require(msg.value >= price, "Insufficient payment for content"); // msg.sender(전송된 이더)가 price이상인지 확인
        require(!(paidContent[msg.sender][contentId]), "This content is already paid for"); // 같은 사용자가 같은 콘텐츠를 이미 결제하였는지 확인

        paidContent[msg.sender][contentId] = true; // 새로운 결제인 경우에 기록
        
        emit PaymentReceived(msg.sender, contentId, msg.value); // PaymentReceived 이벤트 발행
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