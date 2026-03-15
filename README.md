# Leaky Git

## Overview

**Leaky Git** is a tool that enumerates GitHub repositories and scans the commit history of each accessible repository for exposed email addresses. While GitHub supports email address privacy to help prevent this information from being exposed, many users are unaware of this feature or do not configure it correctly. As a result, personal names and email addresses are often unknowingly disclosed publicly.

Note: GitHub's API enforces rate limiting. They provide free API tokens, and it is strongly recommended that you generate and use your own personal access token (https://github.com/settings/tokens) when using this tool.

---

## Usage

The script accepts input either as a command-line argument or via standard input (stdin):

```
python3 leaky-git.py --username "<USERNAME>"
echo "<USERNAME>" | python3 leaky-git.py
```

As mentioned previously, using a GitHub API token is highly recommended. A personal access token can be supplied in a similar manner:
```
python3 leaky-git.py --username "<USERNAME>" --token "<TOKEN>"
echo "<USERNAME>" | python3 leaky-git.py --token "<TOKEN>"
```

Additional options are also available, such as limiting the total number of requests, enabling the parsing of forked repositories, or enabling verbose output.
```
python3 leaky-git.py --username "<USERNAME>" --max-requests 10
python3 leaky-git.py --username "<USERNAME>" --include-forks
python3 leaky-git.py --username "<USERNAME>" --verbose
```

## Local Repositories
For local repositories, you can achieve similar results using the Git CLI:
```
git log --all --pretty=format:'%an <%ae>%n%cn <%ce>' | sort -u
```
