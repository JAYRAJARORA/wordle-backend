# Imports
import dataclasses
import random
import textwrap
import uuid
import databases
import toml
from quart import Quart, g, request, abort, jsonify
from quart_schema import QuartSchema, RequestSchemaValidationError, validate_request, tag


# Initialize the app
app = Quart(__name__)
QuartSchema(app, tags=[
                       {"name": "Games", "description": "APIs for creating a game and playing a game for a particular user"},
                       {"name": "Statistics", "description": "APIs for checking game statistics for a user"},
                       {"name": "Root", "description": "Root path returning html"},
                       {"name": "Leaderboard", "description":"TO display leaderboard"}])
app.config.from_file(f"./etc/wordle.toml", toml.load)


@dataclasses.dataclass
class Word:
    guess: str


# Establish database connection
async def _get_db():
    db = getattr(g, "_sqlite_db", None)
    if db is None:
        db = g._sqlite_db = databases.Database(app.config["DATABASES"]["GAME_URL"])
        await db.connect()
    return db


# Terminate database connection
@app.teardown_appcontext
async def close_connection(exception):
    db = getattr(g, "_sqlite_db", None)
    if db is not None:
        await db.disconnect()


@tag(["Root"])
@app.route("/", methods=["GET"])
async def index():
    """ Root path, returns HTML """
    return textwrap.dedent(
        """
        <h1>Wordle Game</h1>
        <p>To play wordle, go to the <a href="http://tuffix-vm/docs">Games Docs</a></p>\n
        """
    )


@tag(["Games"])
@app.route("/games", methods=["POST"])
async def create_game():
    """ Create a game """
    db = await _get_db()
    username = request.authorization.username

    # Open a file and load json from it
    res = await db.fetch_one(
        """
        SELECT count(*) count FROM correct_words
        """
    )
    length = res.count
    uuid1 = str(uuid.uuid4())
    print(uuid1)
    game_id = await db.execute(
        """
        INSERT INTO games(game_id, username, secret_word_id) 
        VALUES(:uuid, :user, :secret_word_id) 
        """, 
        values={"uuid": uuid1, "user": username, "secret_word_id": random.randint(1, length)}
    )

    return {"game_id": uuid1, "message": "Game Successfully Created"}, 200


@validate_request(Word)
@tag(["Games"])
@app.route("/games/<string:game_id>", methods=["POST"])
async def play_game(game_id):
    """ Play the game (creating a guess) """
    data = await request.json
    db = await _get_db()

    username = request.authorization.username

    return await play_game_or_check_progress(db, username, game_id, data["guess"])


@tag(["Games"])
@app.route("/games/<string:game_id>", methods=["GET"])
async def check_game_progress(game_id):
    """ Check the state of a game that is in progress. If game is over show whether user won/lost and no. of guesses """
    db = await _get_db()
    username = request.authorization.username

    return await play_game_or_check_progress(db, username, game_id)


@tag(["Statistics"])
@app.route("/games", methods=["GET"])
async def get_in_progress_games():
    """ Check the list of in-progress games for a particular user """
    db = await _get_db()
    username = request.authorization.username

    # showing only in-progress games
    games_output = await db.fetch_all(
        """
        SELECT guess_remaining, game_id, state 
        FROM games 
        WHERE username =:username AND state = :state 
        """, 
        values={"username": username, "state": 0}
    )

    in_progress_games = []
    for guess_remaining, game_id, state in games_output:
        in_progress_games.append({
            "guess_remaining": guess_remaining,
            "game_id": game_id
        })

    return in_progress_games


@tag(["Statistics"])
@app.route("/games/statistics", methods=["GET"])
async def statistics():
    """ Checking the statistics for a particular user """
    db = await _get_db()
    username = request.authorization.username

    res_games = await db.fetch_all(
        """
        SELECT state, count(*)
        FROM games 
        WHERE username=:username 
        GROUP BY state
        """,
        values={"username": username}
    )
    states = {0: 'In Progress', 1: 'Win', 2: "Loss"}
    games_stats = {}
    for state, count in res_games:
        games_stats[states[state]] = count

    return games_stats


async def play_game_or_check_progress(db, username, game_id, guess=None):
    states = {0: 'In Progress', 1: 'Win', 2: "Loss"}
    games_output = await db.fetch_one(
        """
        SELECT correct_words.correct_word secret_word, guess_remaining, state 
        FROM games join correct_words WHERE username=:username 
        AND game_id=:game_id AND correct_words.correct_word_id=games.secret_word_id
        """,
        values={"game_id": game_id, "username": username}
    )

    if not games_output:
        abort(400, "No game with this identifier for your username")

    if games_output["state"] != 0:
        return {"number_of_guesses": 6 - games_output["guess_remaining"],
                "decision": states.get(games_output["state"])}, 200

    secret_word = games_output["secret_word"]
    state = 0
    guess_remaining = games_output["guess_remaining"]

    if guess:
        if len(guess) != 5:
            abort(400, "Bad Request: Word length should be 5")
        # when the user guessed the correct word
        if guess == secret_word:
            state = 1
            final_dec = "Win"

        valid_word_output = await db.fetch_one(
            """
            SELECT valid_word_id
            FROM valid_words 
            WHERE valid_word =:word
            """,
            values={"word": guess}
        )
        if not valid_word_output:
            if not state:
                abort(400, "Bad Request: Not a valid guess")

        # Decrement the guess remaining
        guess_remaining = guess_remaining - 1

        # Game is over, update the game
        if guess_remaining == 0 or state:
            # user lost the game
            if guess_remaining == 0 and state == 0:
                state = 2
                final_dec = "Loss"
            await db.execute(
                """
                UPDATE games 
                SET guess_remaining=:guess_remaining, state=:state
                WHERE game_id=:game_id
                """,
                values={"guess_remaining": guess_remaining, "game_id": game_id, "state": state}
            )
            return {"game_id": game_id, "number_of_guesses": 6 - guess_remaining, "decision": states[state]}, 200
        else:
            await db.execute(
                """
                UPDATE games
                SET guess_remaining=:guess_remaining
                WHERE game_id=:game_id
                """,
                values={"guess_remaining": guess_remaining, "game_id": game_id}
                )

            guess_number = 6 - guess_remaining
            valid_word_id = valid_word_output.valid_word_id
            await db.execute(
                """
                INSERT INTO guesses(game_id, valid_word_id, guess_number)
                VALUES(:game_id, :valid_word_id, :guess_number)
                """,
                values={"game_id": game_id, "valid_word_id": valid_word_id, "guess_number": guess_number}
            )
        if(state == 1 or state == 2):
            if(state == 1):
                final_score = guess_remaining+1
            else:
                final_score = 0
            await db.execute(
                """
                INSERT INTO results(game_id, username, decision, final_score)
                VALUES(:game_id, :username, :decision, :final_score)
                """,
                values={"game_id": game_id, "username": username, "decision": final_dec, "final_score": final_score}
            )
    # Prepare the response
    guess_output = await db.fetch_all(
        """
        SELECT guess_number, valid_words.valid_word 
        FROM guesses 
        JOIN valid_words 
        WHERE game_id=:game_id AND valid_words.valid_word_id=guesses.valid_word_id
        ORDER BY guess_number
        """,
        values={"game_id": game_id}
    )
    guesses = []
    for guess_number, valid_word in guess_output:
        correct_positions, incorrect_positions = compare(secret_word, valid_word)
        guesses.append(
            {
                "guess": valid_word,
                "guess_number": guess_number,
                "correct_positions": dict(correct_positions),
                "incorrect_positions:": dict(incorrect_positions),
            }
        )

    return {"guesses": guesses, "guess_remaining": guess_remaining, "game_state": states[state]}, 200


# Function to compare the guess to answer.
def compare(secret_word, guess):
    secret_word_lst = [i for i in enumerate(secret_word)]
    guess_list = [i for i in enumerate(guess)]

    temp_correct_positions = []
    correct_positions = []
    incorrect_positions = []
    for i in range(0, len(secret_word)):
        if guess_list[i][1] == secret_word_lst[i][1]:
            temp_correct_positions.append(guess_list[i])
            correct_positions.append(((guess_list[i][0] + 1), guess_list[i][1]))

    secret_word_lst = [i for i in secret_word_lst if i not in temp_correct_positions]
    guess_list = [i for i in guess_list if i not in temp_correct_positions]

    for i in range(len(guess_list)):
        for j in range(len(secret_word_lst)):
            # found a character which is in a different position
            if guess_list[i][1] == secret_word_lst[j][1]:
                incorrect_positions.append((guess_list[i][0] + 1, guess_list[i][1]))
                secret_word_lst.pop(j)
                break

    return correct_positions, incorrect_positions

@tag(["Leaderboard"])
@app.route("/leaderboard", methods=["GET"])
async def leader_board():
    """ Check the list of users in Top 10 of the leaderboard based on average scores """
    db = await _get_db()
    username = request.authorization.username

    # showing only completed games
    usernames = await db.fetch_all(
        """
        SELECT distinct(username)
        FROM results 
        ORDER BY username ASC
        """
    )   
    result_games = []
    for username in usernames:
        all_results = await db.fetch_all(
            """
            SELECT final_score
            FROM results 
            WHERE username=:username  
            """, 
            values={"username":username[0]}
        )
        total = 0
        count = 0
        for final_score in all_results:
            total = total + final_score[0]
            count = count + 1
        average = total/count
        result_games.append({
            "username": username[0],
            "average": average
        })

    return result_games

@tag(["Leaderboard"])
@app.route("/leaderboard/<string:game_id>", methods=["GET"])
async def games_result(game_id):
    """ Fetch the final result of the users game using the game id """
    db = await _get_db()
    username = request.authorization.username

    # showing only completed games
    games_output = await db.fetch_all(
        """
        SELECT game_id, username, decision, final_score 
        FROM results 
        WHERE game_id =:game_id
        """, 
        values={"game_id":game_id}
    )

    result_game = []
    for game_id, username, decision, final_score in games_output:
        result_game.append({
            "game_id": game_id,
            "username": username,
            "decision": decision,
            "final_score": final_score
        })
 
    return result_game
    
# Error status: Client error.
@app.errorhandler(RequestSchemaValidationError)
def bad_request(e):
    return {"error": str(e.validation_error)}, 400


# Error status: Cannot process request.
@app.errorhandler(409)
def conflict(e):
    return {"error": str(e)}, 409


# Error status: Unauthorized client.
@app.errorhandler(401)
def unauthorized(e):
    return {}, 401, {"WWW-Authenticate": "Basic realm='Wordle Site'"}


# Error status: Cannot or will not process the request.
@app.errorhandler(400)
def bad_request(e):
    return jsonify({'message': e.description}), 400