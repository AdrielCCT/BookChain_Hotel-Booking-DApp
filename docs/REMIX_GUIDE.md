Setting up and testing Hotel Booking Smart Contracts

Local Network Environment

Start the local development blockchain and the script to monitor transactions and funded accounts in the background.

Contract Compilation

1. Start your preferred IDE and create a new project and smart contract source file.

2. Paste the implementation.

3. Go to the compiler settings and select an appropriate version for your blockchain node.

4. Set the target environment for the local node and compile.

Deployment and Hotel Setup

1. In your development IDE, connect your blockchain environment to the local blockchain via an external provider on your localhost. Make sure you can see a list of pre-funded accounts.

2. Choose your main admin account and deploy your smart contract. Keep note of the contract’s address to confirm deployment.

3. To finish setup as the hotel owner, change to the account that holds the hotel and add hotel details (like hotel name) and details on rooms, including the cost of booking a room per night. Record the starting date and time for hotel bookings in the system.

Booking and Escrow

1. Change your account to that of a customer. Start the process of booking a room. To determine the booking price, enter your planned length of stay. Input the price as the transaction value. Use your customer account to finalize the booking.

2. In the finalization, input your hashed customer data to maintain your booking's data privacy.

3. Confirm that the booking has taken place and the escrow has successfully held the payment by reviewing the transaction record and the state of your contract.
4. Security Rules and Validation

Verify constraints with a system account.

Entering overlapping reservation dates produces a “room unavailable” error.

Entering a transaction with the incorrect price results in a “price mismatch” error.

An authorization error results when a reservation not belonging to you is cancelled.

Digital Signature Verification of Check-In

With the dedicated helper script, generate cryptographic check-in signatures. The transaction will revert if an unauthorized account attempts to use the signature. Using a registered guest’s generated signature will result in successful check-in of the hotel, and the check-in status will change and funds will be transferred to the withdrawal pending balance. The hotel will then be able to withdraw the earnings.

Cancellation Policy

Create a reservation using a guest account and then create a cancellation request for it immediately. If the request is created long enough before the check-in date, a full refund without penalty will be provided.

Automated Verification

Observe all created blocks and entered transactions in the active blockchain terminal. Run the automated execution scripts for all test cases, and verify all contract behaviors for every possible scenario.
Observe all created blocks and entered transactions in the active blockchain terminal. Run the automated execution scripts for all test cases, and verify all contract behaviors for every possible scenario.