# DBConnect

Python wrapper class to make connecting to RDBMS sources and producing pandas DataFrames easy!
With this class you can connect securely to Oracle, SQL Server, PostgreSQL and MySQL database sources.
Connection details for each RDBMS source are maintained in a JSON config file, and encryption tools
are provided to encrypt the passwords.
Create objects using this class for each DB connection you need, and then leverage one-size-fits-all 
methods such as `connect()`, `runSql()` and `makeDataFrame()` for any of the supported RDBMS sources.

## Installation

This class has been developed and tested against Python 3.10.3

It requires the following libraries:
* `pandas`
* `oracledb`
* `pymssql`
* `psycopg2`
* `MySQLdb`

Use `pip` to install them if you don't already have them.

## Configuration

1. Navigate to the DBConnect.py script.
2. Open a Python shell and run the following to generate your encryption key:

```
from DBConnect import genEncryptionKey
genEncryptionKey()
```

Copy the output value and then create a new environment variable called DBCONNECT_ENCRYPT_KEY with
this output value.

3. Navigate to the ./config directory and edit the database-config-plaintext.json file.
4. Create as many entries as you need for the RDBMS sources you intend to use. Example entries are provided for reference.
   Note that the `connection-name` should be unique within the file and across RDBMS types. If you have two entries called
   'MYDB' then DBConnect will simply use the first one it sees.
5. Return to the Python shell and run the following:

```
from DBConnect import encryptConfigFile
encryptConfigFile()
```

6. This will produce a new file under the ./config directory called database-config.json with all passwords encrypted.

## Usage

You can now use the DBConnect class in your own Python programs. Simply import it into existing or new Python files using:

`from DBConnect import DBConnect`

To create a connection, for example an Oracle connection, simply use:

`oOraConnect = DBConnect('ORACLE_EXAMPLE')`

This creates an Oracle connection to the database configured in database-config.json with a `connection-name` of ORACLE_EXAMPLE.
By default, the connection is also opened. You can check the status of a connection using:

`oOraConnect.status()`

This will return `True` if the connection is open or `False` if it is closed. If you don't want your connection to be automatically
open at the point of instantiation, set the `activate` parameter to `False`, for example:

`oOraConnect = DBConnect('ORACLE_EXAMPLE', activate=False)`

You can execute any SQL statement you wish by using the `runSql()` method, for example:

`oOraConnect.runSql("SELECT * FROM USER_TABLES")`

The result will be returned and also stored in the object's `lastResult` attribute. Results are returned in a nested list of dictionaries.
Note that the `runSql()` method will automatically open a connection if it is closed at the point of calling it.
By default, `runSql()` does *not* commit SQL transactions; to override this behaviour, you can set the `commit` parameter to `True`.
By default, `runSql()` will close the connection after execution; to override this behaviour, set the `kill` parameter to `False`.
There is also an optional `one` parameter if you know your query will only produce a single row and you just want that row returned as
an unnested dictionary. For example:

`oOraConnect.runSql("SELECT COUNT(*) AS count_rows FROM USER_TABLES", one=True)`

Be sure to always include column aliases if you are not selecting directly from a column.

To create a pandas DataFrame, ensure you have first used the `runSql()` method to execute a SELECT statement. Then use the `makeDataFrame()` method.
For example:

```
oOraConnect.runSql("SELECT * FROM USER_TABLES")
oOraConnect.makeDataFrame()
```

The DataFrame will be returned and also retained in the DBConnect object's `dataFrame` attribute.

You can clear both the `lastResult` and `dataFrame` attributes of the DBConnect object by using the `flush()` method.

Note that all of the above methods can be used regardless of the RDBMS source: the DBConnect wrapper handles all the specifics of each RDBMS and its
library. If you wish to use specific methods that are not covered here, you can always make use of the `connection` attribute of the DBConnect object.
For example, if you want to bypass the `runSql()` method and use the underlying library, you could create a cursor as follows:

```
oOraConnect = DBConnect('ORACLE_EXAMPLE')
cur = oOraConnect.connection.cursor()
```

This can be useful if you just want to use DBConnect as a simple way of supporting JSON-configurable, encrypted connections.