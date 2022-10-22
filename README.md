# CPSC 449 Project 1 Objective
- Develop back-end REST APIs for a game similar to Wordle.

## Project Members
- Abhishek Nagesh Shinde
- Parva Parikh
- Jayraj Arora
- Brent Pfefferle

## Development Environment
- Tuffix 2020 (Linux)

## Technologies Used
- Python
- Quart
- Sqlite3
- Foreman
- Databases
- Quart-Schema
- Curl
- HTTPie

## REST API for the Project
- Register a user
- Authenticate a user 
- Start a new game
- Guess a five-letter word
- Retrieve the state of a game in progress
- List the games in progress for a user
- Check the statistics for a particular user
- Password hashing and decoding.

## How to Use
- Go to the project's directory
- Run the command ```./bin/init.sh``` to initialize the database
- Run the command ```foreman start``` to start the application server (http://127.0.0.1:5000)
- Run/test the REST endpoints using the API documentation generated by Quart-Schema(http://127.0.0.1:5000/docs) 
or using an API client like httpie or curl.
- In order to run via httpie, use the following the commands:
  - For POST /users API(creating a user): ```http 127.0.0.1:5000/users username=test password=test```
  - For GET/login(authenticate a user): ```http --auth test:test 127.0.0.1:5000/login```
  - For POST /users/{username}/games(create a game): ```http POST 127.0.0.1:5000/users/test/games```
  - For GET /users/{username}/games/{game_id}(check the state of a game): ```http GET 127.0.0.1:5000/users/test/games/<enter game id>```
  - For POST /users/{username}/games/{game_id}(play a game): ```http POST 127.0.0.1:5000/users/test/games/<enter game id> guess=cakes```
  - For GET /users/{username}/games(get the list of in-progress games): ```http 127.0.0.1:5000/users/test/games``` 
  - For GET /users/{username}/statistics(check the statistics of the user): ```http 127.0.0.1:5000/users/test/statistics```

