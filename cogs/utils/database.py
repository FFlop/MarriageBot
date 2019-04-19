from random import choices
from asyncio import create_subprocess_exec, get_event_loop
from logging import getLogger

from discord import Member
from asyncpg import connect as _connect, Connection, create_pool as _create_pool
from asyncpg.pool import Pool


RANDOM_CHARACTERS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890-_'
logger = getLogger('marriagebot-db')



class DatabaseConnection(object):

    config = None
    pool = None


    def __init__(self, connection:Connection=None):
        self.conn = connection


    @classmethod
    async def create_pool(cls, config:dict):
        cls.config = config
        cls.pool = await _create_pool(**config)


    async def __aenter__(self):
        self.conn = await self.pool.acquire()
        return self


    async def __aexit__(self, exc_type, exc, tb):
        await self.pool.release(self.conn)
        self.conn = None
        del self


    async def __call__(self, sql:str, *args):
        '''
        Runs a line of SQL using the internal database
        '''

        # Runs the SQL
        logger.debug(f"Running SQL: {sql} ({args!s})")
        x = await self.conn.fetch(sql, *args)

        # If it got something, return the dict, else None
        if x:
            return x
        if 'select' in sql.casefold() or 'returning' in sql.casefold():
            return []
        return None


    async def destroy(self, user_id:int):
        '''
        Removes a given user ID form all parts of the database
        '''

        await self('UPDATE marriages SET valid=False WHERE user_id=$1 OR partner_id=$1', user_id)
        await self('DELETE FROM parents WHERE child_id=$1 OR parent_id=$1', user_id)


    async def make_id(self, table:str, id_field:str) -> str:
        '''
        Makes a random ID that hasn't appeared in the database before for a given table
        '''

        while True:
            id_number = ''.join(choices(RANDOM_CHARACTERS, k=11))
            x = await self(f'SELECT * FROM {table} WHERE {id_field}=$1', id_number)
            if not x:
                break
        return id_number


    async def marry(self, instigator:Member, target:Member, guild_id:int, marriage_id:str=None):
        '''
        Marries two users together
        Remains in the Database class solely as you need the "idnumber" field.
        '''

        if marriage_id == None:
            id_number = await self.make_id('marriages', 'marriage_id')
        else:
            id_number = marriage_id
        # marriage_id, user_id, user_name, partner_id, partner_name, valid
        await self(
            'INSERT INTO marriages (marriage_id, user_id, partner_id, valid, guild_id) VALUES ($1, $2, $3, TRUE, $4)',
            id_number,
            instigator.id,
            target.id,
            guild_id,
        )
        if marriage_id == None:
            await self.marry(target, instigator, guild_id, id_number)  # Run it again with instigator/target flipped
