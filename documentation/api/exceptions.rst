`awwparse.exceptions`
=====================

.. module:: awwparse.exceptions


User errors
-----------

Errors that are caused by wrong usage of the command line interface.

.. autoexception:: CLIError
   :members:

.. autoexception:: UnexpectedArgument
   :members:

.. autoexception:: ArgumentMissing
   :members:

.. autoexception:: UserTypeError
   :members:

.. autoexception:: CommandMissing
   :members:

.. autoexception:: PositionalArgumentMissing
   :members:


Programming errors
------------------

Errors that are raised as a result of (wrong) usage of the API.

.. autoexception:: Conflict
   :members:

.. autoexception:: OptionConflict
   :members:

.. autoexception:: CommandConflict
   :members:

.. autoexception:: ArgumentConflict
   :members:


Internal exceptions
-------------------

Exceptions used internally in case of certain events.

.. autoexception:: EndOptionParsing
   :members:
