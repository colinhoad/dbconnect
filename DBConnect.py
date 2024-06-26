# Author:  Colin James Hoad
# Created: 28.04.2024

# General libraries
import json
import logging
import os
import sys
import pandas as pd
from enum import Enum
from cryptography.fernet import Fernet
# RDBMS libraries
import oracledb  # Oracle library
import pymssql  # SQL Server library
import psycopg2  # PostgreSQL library
import psycopg2.extras  # PostgreSQL cursors extension
import MySQLdb  # MySQL library
import MySQLdb.cursors  # MySQL cursors extension


def exceptionHandler(exception_type, exception, traceback):
    """
    Formats exceptions to avoid unnecessary traceback messages.

    Parameters:
        exception_type: the type of exception, e.g. ValueError, DatabaseError etc.
        exception: the custom print message to accompany the exception.
        traceback: empty parameter to prevent traceback printing.
    """
    print("%s: %s" % (exception_type.__name__, exception))


def genEncryptionKey():
    """
    Generates a Fernet encryption key to be used for encrypting and decrypting database passwords.
    Use this function to generate the encryption key to be used as the value for the DBCONNECT_ENCRYPT_KEY
    environment variable.

    Returns:
        eKey (str): encryption key in decoded string format.
    """
    key = Fernet.generate_key()
    eKey = key.decode('utf-8')
    return eKey


def encryptConfigFile(eKey=os.environ.get('DBCONNECT_ENCRYPT_KEY', 'encryption_key_not_set'), 
                      configFile=os.path.abspath(os.path.join('config', 'database-config-plaintext.json'))):
    """
    Reads in the JSON config file and then overwrites it back to file with all passwords encrypted.

    Parameters:
        eKey (str): the Fernet encryption key to be used for encrypting the passwords.
        configFile (str): fully qualified path to the JSON config file.
    """
    encryptionKey = Fernet(eKey)
    with open(configFile, 'r') as dbConfigFile:
        connectionEntries = json.load(dbConfigFile)  # load entire JSON file into nested dictionary
    dbConfigFile.close()  # close the JSON file
    for entry in connectionEntries:
        entry["password"] = encryptionKey.encrypt(entry["password"].encode()).decode('utf-8')
    encryptedConfigFile = configFile[:-15] + '.json'
    with open(encryptedConfigFile, 'w') as dbConfigFile:
        json.dump(connectionEntries, dbConfigFile, indent=2)
    dbConfigFile.close()  # close the JSON file


class DBType(Enum):
    ORACLE = 'oracle'
    SQL_SERVER = 'sqlserver'
    POSTGRESQL = 'postgresql'
    MYSQL = 'mysql'


class DBConnect:
    """
    A class representing a connection to a relational database.

    Attributes:
        name (str): The name of the database connection as defined in the JSON config file.
        eKey (str): A string-based encryption key needed for decrypting passwords in the JSON config file.
                    This will default to the environment variable DBCONNECT_ENCRYPT_KEY which should be set prior
                    to using this class. Use the genEncryptionKey() function to generate a new encryption
                    key and then set this as the value of DBCONNECT_ENCRYPT_KEY at the OS level.
        dKey (Fernet): A Fernet-type encryption key derived from eKey.
        configFile (str): Fully qualified path to the JSON config file (default is ./config relative to the class file).
                          Ensure you have encrypted the JSON config file using the encryptConfigFile() function with
                          the encryption key generated by genEncryptionKey() and which has been set as the value of the
                          DBCONNECT_ENCRYPT_KEY environment variable.
        activate (bool): Indicates whether to open a connection on instantiation (default is True).
        connDetails (dict): A dictionary of the connection's details read from the JSON config file on creation.
        connection (obj): A child object representing the database connection of the specific RDBMS.
        lastResult (list): The result of the most recently executed SQL statement, stored as a list of dictionaries.
        dataFrame (pd.DataFrame): The lastResult converted to a pandas DataFrame.
    """

    sys.excepthook = exceptionHandler

    def __init__(self, connName, eKey=os.environ.get('DBCONNECT_ENCRYPT_KEY', 'encryption_key_not_set'),
                 configFile=os.path.abspath(os.path.join('config', 'database-config.json')), activate=True):
        """
        Initialises a DBConnect object with the capability to run SQL statements.

        Parameters:
            connName (str): The name of the database connection as defined in the JSON config file.
            eKey (str): The encryption key needed for decrypting passwords in the JSON config file.
            activate (bool): If true (default) the connection will be opened on instantiation.
        """
        self.name = connName
        self.eKey = eKey
        try:
            self.dKey = Fernet(eKey)
        except ValueError as err:
            logging.error(err)
            print(f"Encryption key is invalid, please ensure DBCONNECT_ENCRYPT_KEY environment variable has been set!")
            sys.exit(-1)
        self.configFile = configFile
        self.activate = activate
        self.connDetails = self._getDetails()
        self.connection = None  # initialise to NoneType
        self.lastResult = None  # initialise to NoneType
        self.dataFrame = None  # initialise to NoneType
        if self.activate:
            self.connect()  # ...then attempt to connect

    def connect(self):
        """
        Creates an open connection object.

        Returns:
            self.connection (object)
        """
        if self.connDetails['rdbms'] == DBType.ORACLE.value:
            try:
                self.connection = self._oracleConnection()
            except oracledb.DatabaseError as err:
                logging.error(err)
                print(f"Unexpected error connecting to {self.name}")
        elif self.connDetails['rdbms'] == DBType.SQL_SERVER.value:
            try:
                self.connection = self._sqlServerConnection()
            except pymssql.DatabaseError as err:
                logging.error(err)
                print(f"Unexpected error connecting to {self.name}")
        elif self.connDetails['rdbms'] == DBType.POSTGRESQL.value:
            try:
                self.connection = self._pgConnection()
            except psycopg2.DatabaseError as err:
                logging.error(err)
                print(f"Unexpected error connecting to {self.name}")
        elif self.connDetails['rdbms'] == DBType.MYSQL.value:
            try:
                self.connection = self._mySqlConnection()
            except MySQLdb.DatabaseError as err:
                logging.error(err)
                print(f"Unexpected error connecting to {self.name}")
        else:
            raise ValueError(f"Unknown database type {self.connDetails['rdbms']} - cannot establish a connection!")

    def disconnect(self):
        """
        Closes an existing open connection object.
        """
        if self.status():
            if self.connDetails['rdbms'] == DBType.ORACLE.value:
                try:
                    self.connection.close()
                except oracledb.DatabaseError as err:
                    logging.error(err)
                    print(f"Unexpected error disconnecting from {self.name}")
            elif self.connDetails['rdbms'] == DBType.SQL_SERVER.value:
                try:
                    self.connection.close()
                except pymssql.DatabaseError as err:
                    logging.error(err)
                    print(f"Unexpected error disconnecting from {self.name}")
            elif self.connDetails['rdbms'] == DBType.POSTGRESQL.value:
                try:
                    self.connection.close()
                except psycopg2.DatabaseError as err:
                    logging.error(err)
                    print(f"Unexpected error disconnecting from {self.name}")
            elif self.connDetails['rdbms'] == DBType.MYSQL.value:
                try:
                    self.connection.close()
                except MySQLdb.DatabaseError as err:
                    logging.error(err)
                    print(f"Unexpected error disconnecting from {self.name}")
            else:
                raise ValueError(f"Unknown database type {self.connDetails['rdbms']} - cannot establish a connection!")

    def status(self):
        """
        Indicates whether a connection is open (True) or closed (False).
        """
        status = False
        if self.connection is None:
            status = False
        elif self.connDetails['rdbms'] == DBType.ORACLE.value:
            try:
                if self.connection.is_healthy():
                    status = True
                else:
                    status = False
            except oracledb.DatabaseError as err:
                logging.error(err)
                print(f"Unexpected error connecting to {self.name}")
        elif self.connDetails['rdbms'] == DBType.SQL_SERVER.value:
            try:
                status = self.connection._conn.connected
            except pymssql.InterfaceError:
                status = False
        elif self.connDetails['rdbms'] == DBType.POSTGRESQL.value:
            if self.connection.closed:
                status = False
            else:
                status = True
        elif self.connDetails['rdbms'] == DBType.MYSQL.value:
            if self.connection.open == 1:
                status = True
            else:
                status = False
        return status

    def runSql(self, sql="", one=False, commit=False, kill=True):
        """
        Executes a SQL statement using the child connection object and returns the results.
        
        Parameters:
            sql (str): the SQL statement to be executed.
            one (bool): indicates whether to return only the first row (default is False)
            commit (bool): indicates whether to execute a COMMIT after executing (default is False)
            kill (bool): indicates whether to close the connection after executing (default is True)
        Returns:
            results (list)
        """
        results = []  # initialise to empty list
        # check if connection open, and if not, establish it
        self.status()
        if not self.status():
            self.connect()
        # based on the RDBMS type, carry out the SQL execution
        # Oracle
        if self.connDetails['rdbms'] == DBType.ORACLE.value:
            cur = self.connection.cursor()
            try:
                cur.execute(sql)
                if cur.description is None:
                    results = [{'Row(s) affected': cur.rowcount}]
                else:
                    columns = [col[0] for col in cur.description]
                    cur.rowfactory = lambda *args: dict(zip(columns, args))
                    results = cur.fetchall()
                if commit:
                    self.connection.commit()
                if kill:
                    self.disconnect()
            except oracledb.DatabaseError as err:
                logging.error(err)
                raise oracledb.DatabaseError(f"Unable to execute SQL statement using Oracle connection {self.name}")
        # SQL Server
        elif self.connDetails['rdbms'] == DBType.SQL_SERVER.value:
            cur = self.connection.cursor(as_dict=True)
            try:
                cur.execute(sql)
                # try to get rows, if exception then assume DML/DDL and return how many rows were affected
                try:
                    results = cur.fetchall()
                except pymssql.OperationalError:
                    results = [{'Row(s) affected': cur.rowcount}]
                if commit:
                    self.connection.commit()
                if kill:
                    self.disconnect()
            except pymssql.DatabaseError as err:
                logging.error(err)
                raise pymssql.DatabaseError(f"Unable to execute SQL statement using SQL Server connection {self.name}")
        # PostgreSQL
        elif self.connDetails['rdbms'] == DBType.POSTGRESQL.value:
            cur = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                cur.execute(sql)
                # check if the cursor selected any rows (e.g. if it's an INSERT then there won't be any rows to fetch)
                if cur.statusmessage[0:6] == 'SELECT' and cur.rowcount > 0:
                    rawResults = cur.fetchall()
                    keys = [i.keys() for i in rawResults]
                    values = [i.values() for i in rawResults]
                    for i in range(len(rawResults)):
                        d = dict(zip(keys[i], values[i]))
                        results.append(d)
                else:
                    results = [{'Row(s) affected': cur.rowcount}]
                if commit:
                    self.connection.commit()
                if kill:
                    self.disconnect()
            except psycopg2.DatabaseError as err:
                logging.error(err)
                raise psycopg2.DatabaseError(f"Unable to execute SQL statement using PostgreSQL connection {self.name}")
        # MySQL
        elif self.connDetails['rdbms'] == DBType.MYSQL.value:
            try:
                cur = self.connection.cursor()
                rowCount = cur.execute(sql)
                results = cur.fetchall()
                results = [i for i in results]  # convert to list for consistency
                # if no rows were returned, assume it was DML/DDL
                if len(results) == 0:
                    results = [{'Row(s) affected': rowCount}]
                if commit:
                    self.connection.commit()
                if kill:
                    self.disconnect()
            except MySQLdb.DatabaseError as err:
                logging.error(err)
                raise MySQLdb.DatabaseError(f"Unable to execute SQL statement using MySQL connection {self.name}")
        else:
            ValueError(f"Unknown database type {self.connDetails['rdbms']} - cannot execute SQL statement!")
        # set lastResults value and return the results
        if one:
            results = results[0]
        self.lastResult = results
        return results

    def flush(self):
        """
        Clears the lastResult and dataFrame attributes.
        """
        self.lastResult = None
        self.dataFrame = None

    def makeDataFrame(self):
        """
        Creates a pandas DataFrame from the lastResult attribute.

        Returns:
            self.dataFrame (pd.DataFrame): a pandas DataFrame of the most recently executed SQL statement.
        """
        if self.lastResult is not None:
            self.dataFrame = pd.DataFrame.from_records(self.lastResult)
            return self.dataFrame
        else:
            raise ValueError("Cannot create DataFrame, no SQL statement has been executed by this object.")

    def _oracleConnection(self):
        """
        Creates a child Oracle connection object.

        Returns:
            oracledb.connect()
        """
        if "dsn" in self.connDetails:
            dsn = self.connDetails["dsn"]
        else:
            dsn = self.connDetails["server"] + ':' + self.connDetails["port"] + '/' + self.connDetails["service-name"]
        try:
            # establish Oracle connection
            oracledb.defaults.fetch_lobs = False  # this allows DBConnect class to read <1GB CLOB data as a string
            return oracledb.connect(user=self.connDetails["username"],
                                    password=self.dKey.decrypt(self.connDetails["password"]).decode(),
                                    dsn=dsn)
        except oracledb.DatabaseError as err:
            logging.error(err)
            print(f"Could not establish Oracle connection for {self.name}")

    def _sqlServerConnection(self):
        """
        Creates a child Microsoft SQL Server connection object

        Returns:
            pymssql.connect()
        """
        try:
            # establish MSSQL connection
            return pymssql.connect(self.connDetails["server"],
                                   self.connDetails["username"],
                                   self.dKey.decrypt(self.connDetails["password"]).decode(),
                                   self.connDetails["database-name"])
        except pymssql.DatabaseError as err:
            logging.exception(err)
            print(f"Could not establish SQL Server connection for {self.name}")

    def _pgConnection(self):
        """
        Creates a child PostgreSQL connection object

        Returns:
            psycopg2.connect()
        """
        try:
            # establish PostgreSQL connection
            return psycopg2.connect(host=self.connDetails["server"],
                                    database=self.connDetails["database-name"],
                                    user=self.connDetails["username"],
                                    password=self.dKey.decrypt(self.connDetails["password"]).decode())
        except psycopg2.DatabaseError as err:
            logging.exception(err)
            print(f"Could not establish PostgreSQL connection for {self.name}")

    def _mySqlConnection(self):
        """
        Creates a child MySQL connection object

        Returns:
            MySQLdb.connect()
        """
        try:
            # establish MySQL connection
            return MySQLdb.Connection(host=self.connDetails["server"],
                                      db=self.connDetails["database-name"],
                                      user=self.connDetails["username"],
                                      passwd=self.dKey.decrypt(self.connDetails["password"]).decode(),
                                      port=int(self.connDetails["port"]),
                                      connect_timeout=20,
                                      cursorclass=MySQLdb.cursors.DictCursor)
        except MySQLdb.DatabaseError as err:
            logging.exception(err)
            print(f"Could not establish MySQL connection for {self.name}")

    def _getDetails(self):
        """
        Populates self.connDetails with connection details harvested from the JSON config file.

        Returns:
            entry (dict)
        """
        configFile = os.path.abspath(os.path.join('config', 'database-config.json'))
        with open(configFile, 'r') as dbConfigFile:
            connectionEntries = json.load(dbConfigFile)  # load entire JSON file into nested dictionary
        dbConfigFile.close()  # close the JSON file
        for entry in connectionEntries:
            if entry["active"] and entry["connection-name"] == self.name:
                return entry
        raise ValueError(f"Unable to find active connection {self.name} in JSON config file")


sys.excepthook = exceptionHandler
