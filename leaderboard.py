# Imports
import textwrap
import toml
from quart import Quart, request, jsonify, abort
from quart_schema import QuartSchema, tag
import redis
import collections

# Initialize the app
app = Quart(__name__)
QuartSchema(app, tags=[
    {"name": "Leaderboard", "description": "APIs for posting the results of the leaderboard service"},
    {"name": "Root", "description": "Root path returning html"}])
app.config.from_file(f"./etc/wordle.toml", toml.load)


def _initialize_redis():
    r = redis.Redis()
    return r


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
@app.route("/results", methods=["POST"])
async def add_game_results():
    """ Posting the results of the game. Pass username, status as win/loss and the number of guesses"""
    data = await request.json
    r = _initialize_redis()
    if 'username' not in data:
        abort(400, "Please enter username")
    if 'status' not in data or data['status'] not in ['win', 'loss']:
        abort(400, "Please pass the status of the game as either win or loss")
    username = data['username']
    status = data['status']
    if status == 'win' and 'guess_number' not in data:
        abort(400, "Please pass the guess number if game status is win")

    # compute score from the number of guess and game status
    if status == 'loss':
        game_score = 0
    else:
        guess_number = int(data['guess_number'])
        game_score = 6 - guess_number + 1

    # if redis key is not created it automatically create a key

    # increment total of the game score by the current game score
    r.hincrby("users:" + username, "total_score", game_score)
    total_score = int(r.hget("users:" + username, "total_score").decode("UTF-8"))

    # increment the number of games by 1
    r.hincrby("users:" + username, "game_count", 1)
    number_of_games = int(r.hget("users:" + username, "game_count").decode("UTF-8"))

    avg_score = total_score / number_of_games

    r.zadd("wordle_leaderboard", {"users:" + username: avg_score})
    return {"Message": "Game results successfully posted."}, 201


@tag(["Leaderboard"])
@app.route("/leaderboard", methods=["GET"])
async def leaderboard():
    """ Retrieve the list of top 10 users of the leaderboard based on their average scores """
    r = _initialize_redis()

    avg_score_result = r.zrevrange("wordle_leaderboard", 0, 9, True)
    # prepare response

    # no users in the redis
    if len(avg_score_result) == 0:
        return "Please post results to retrieve the top 10 users by average score", 200
    print(avg_score_result)
    leaderboard_result = []

    for user, score in avg_score_result:
        user = user.decode('UTF-8').split(':')[1]
        leaderboard_result.append({"username": user,  "score": score})

    return leaderboard_result, 200


# Error status: Cannot or will not process the request.
@app.errorhandler(400)
def bad_request(e):
    return jsonify({'message': e.description}), 400
