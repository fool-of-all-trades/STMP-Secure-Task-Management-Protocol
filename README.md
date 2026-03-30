# Secure Task Manager (STMP)

Secure Task Manager is a client-server application built on top of a custom-designed application-layer protocol.

The project focuses on secure and reliable task management over TCP + TLS 1.3, with support for user registration, authentication, session handling, reconnection, duplicate request detection, and structured error handling.

## Overview

The system allows users to:

- register a new account
- log in securely
- create, update, and delete personal tasks
- maintain an active session
- resume a session after a temporary connection loss

## Protocol Highlights

**STMP/1.0** is a custom application-layer protocol with:

- TCP + TLS 1.3 transport
- length-prefixed JSON messages
- request correlation using `request_id`
- session management via `session_token`
- replay protection using `request_id` and `timestamp`
- keep-alive using `PING / PONG`
- reconnect support with `RESUME_SESSION`
- structured protocol and business error codes

Example message types include:

- `HELLO`, `HELLO_OK`
- `REGISTER`, `REGISTER_OK`, `REGISTER_FAIL`
- `LOGIN`, `LOGIN_OK`, `LOGIN_FAIL`
- `RESUME_SESSION`
- `CREATE_TASK`, `UPDATE_TASK`, `DELETE_TASK`
- `TASK_CREATED`, `TASK_UPDATED`, `TASK_DELETED`
- `PING`, `PONG`
- `ERROR`, `BYE`

## Security Features

The project includes several security-oriented mechanisms:

- encrypted communication via TLS 1.3
- password-based authentication
- time-limited session tokens
- access control to user-owned tasks only
- duplicate request detection
- replay protection
- rate limiting and message size limits
- diagnostic logging without exposing passwords or tokens

## Planned / Implemented Application Architecture

The application follows a client-server model and is organized around the following components:

- Client application (CLI/GUI)
- Application server
- Authentication/session module
- Data storage
- Logging/diagnostics module

High-level flow:

1. user performs an action in the client
2. client builds an STMP message
3. message is sent over TCP + TLS
4. server validates and processes the request
5. data is read or updated
6. server sends an STMP response
7. client updates the user view accordingly

## Authors

- Joanna Kliś
- Martyna Huza
- Wiktoria Herczyk