---
title: "Authentication"
sidebar_label: Introduction
---

Home Assistant has a built-in authentication system allowing different users to interact with Home Assistant. The authentication system consist of various parts.

<img class='invertDark' src='/img/en/auth/architecture.png'
  alt='Overview of how the different parts interact' />

## Authentication providers

An authentication provider is used for users to authenticate themselves. It's up to the authentication provider to choose the method of authentication and the backend to use. By default we enable the built-in Home Assistant authentication provider which stores the users securely inside your configuration directory.

The authentication providers that Home Assistant will use are specified inside `configuration.yaml`. It is possible to have multiple instances of the same authentication provider active. In that case, each will be identified by a unique identifier. Authentication providers of the same type will not share credentials.

## Credentials

Credentials store the authentication of a user with a specific authentication provider. It is produced when a user successfully authenticates. It will allow the system to find the user in our system. If the user does not exist, a new user will be created. This user will not be activated but will require approval by the owner.

It is possible for a user to have multiple credentials linked to it. However, it can only have a single credential per specific authentication provider.

## Users

Each person is a user in the system. To log in as a specific user, authenticate with any of the authentication providers that are linked to this user. When a user logs in, it will get a refresh and an access token to make requests to Home Assistant.

### Owner

The user that is created during onboarding will be marked as "owner". The owner is able to manage other users and will always have access to all permissions.

## Groups

Users are a member of one or more groups. Group membership is how a user is granted permissions.

## Permission policy

This is the permission policy that describes to which resources a group has access. For more information about permissions and policies, see [Permissions](auth_permissions.md).

## Access and refresh tokens

Applications that want to access Home Assistant will ask the user to start an authorization flow. The flow results in an authorization code when a user successfully authorizes the application with Home Assistant. This code can be used to retrieve an access and a refresh token. The access token will have a limited lifetime while refresh tokens will remain valid until a user deletes it.

The access token is used to access the Home Assistant APIs. The refresh token is used to retrieve a new valid access token.

### Refresh token types

There are three different types of refresh tokens:

- *Normal*: These are the tokens that are generated when a user authorizes an application. The application will hold on to these tokens on behalf of the user.
- *Long-lived Access Token*: These are refresh tokens that back a long lived access token. They are created internally and never exposed to the user.
- *System*: These tokens are limited to be generated and used by system users like Home Assistant OS and the Supervisor. They are never exposed to the user.
