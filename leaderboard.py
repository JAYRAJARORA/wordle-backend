# Imports
import dataclasses
import textwrap
import databases
import toml
from quart import Quart, g, request, jsonify
from quart_schema import QuartSchema, RequestSchemaValidationError, tag


# Initialize the app
app = Quart(__name__)
QuartSchema(app, tags=[
                       {"name": "Games", "description": "APIs for creating a game and playing a game for a particular user"},
                       {"name": "Statistics", "description": "APIs for checking game statistics for a user"},
                       {"name": "Root", "description": "Root path returning html"}])
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

@tag(["Leaderboard"])
@app.route("/leaderboard/<string:game_id>", methods=["GET"])
async def games_result(game_id):
    """ Fetch the final result of the users game using the game id """
    db = await _get_db()
    username = request.authorization.username

    # showing only in-progress games
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
    #sorted_res = []
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
        #sorted_res = sorted(key=lambda x: x.average, reverse=True)
    return result_games



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