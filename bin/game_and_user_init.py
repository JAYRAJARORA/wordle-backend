# Imports
import random
import asyncio
import databases
import toml
from quart import Quart
from quart_schema import QuartSchema
import uuid
import hashlib
import secrets
import base64

# Encryption type.
ALGORITHM = "pbkdf2_sha256"

# Initialize app
app = Quart(__name__)
QuartSchema(app)
app.config.from_file(f"../etc/wordle.toml", toml.load)


# Establish database connection.
async def _get_game_db():
    db = databases.Database(app.config["DATABASES"]["GAME_URL"])
    await db.connect()
    return db


# Establish database connection.
async def _get_user_db():
    db = databases.Database(app.config["DATABASES"]["USER_URL"])
    await db.connect()
    return db


# insert into query for games and guesses table
async def insert_into_games_sql(username):

    db = await _get_game_db()
    res = await db.fetch_one(
        """
        SELECT count(*) count 
        FROM correct_words
        """
    )
    length = res.count
    
    uuid1 = str(uuid.uuid4())
    
    # 1
    await db.execute(
        """
        INSERT INTO games(game_id, username, secret_word_id)
        VALUES(:uuid, :users, :secret_word_id)
        """, 
        values={"uuid": uuid1, "users": username, "secret_word_id": random.randint(1, length)}
    )

    res = await db.fetch_one(
        """
        SELECT count(*) count
        FROM valid_words
        """
    )
    length = res.count

    await db.execute(
        """
        INSERT INTO guesses(game_id, valid_word_id, guess_number)
        VALUES(:game_id, :valid_word_id, :guess_number)
        """,
        values={"game_id": uuid1, "valid_word_id": random.randint(1, length), "guess_number": 1}
    )


# insert into queries user table
async def insert_into_users_sql(username):
    db = await _get_user_db()

    user = {"username": username, "password": "abc"}
    user["password"] = hash_password(user["password"])
    
    # Insert into database
    await db.execute(
        """
        INSERT INTO users(username, password) values (:username, :password)
        """,
        user
    )


# Hash a given password using pbkdf2.
def hash_password(password, salt=None, iterations=260000):
    if salt is None:
        salt = secrets.token_hex(16)
    assert salt and isinstance(salt, str) and "$" not in salt
    assert isinstance(password, str)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    b64_hash = base64.b64encode(pw_hash).decode("ascii").strip()
    return "{}${}${}${}".format(ALGORITHM, iterations, salt, b64_hash)


# Run when executed as script.
if __name__ == "__main__":
    user1 = 'dummy'
    user2 = 'money'
    
    print("Loading data into users table")
    asyncio.run(insert_into_users_sql(user1))
    asyncio.run(insert_into_users_sql(user2))

    print("Loading data into games table")
    asyncio.run(insert_into_games_sql(user1))
    asyncio.run(insert_into_games_sql(user1))
    asyncio.run(insert_into_games_sql(user2))
    asyncio.run(insert_into_games_sql(user2))

    print("Loading of tables complete")
