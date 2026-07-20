---
description: Run all automated tests
agent: build
---

Run all automated tests in this project. Detect the testing framework or runner by checking the following, in order:

1. Node.js — Check package.json for scripts like `test`, `vitest`, `jest`, `mocha`, `ava`, `tap`.
2. Python — Check for `pytest`, `tox`, `unittest` in pyproject.toml, setup.cfg, tox.ini, or a Makefile with test targets.
3. Java — Check for Maven (`pom.xml` — `mvn test`), Gradle (`build.gradle` or `build.gradle.kts` — `gradle test`). Look for JUnit, TestNG in build files. Spring Boot projects usually have `spring-boot-starter-test`. Quarkus projects use `quarkus-junit5`.
4. .NET — Check for `.csproj` or `.sln` files. Look for NUnit (`nunit` packages), xUnit (`xunit` packages), or MSTest references. Run with `dotnet test`.
5. Go — Check for `go.mod` — run `go test ./...`.
6. Rust — Check for `Cargo.toml` — run `cargo test`.
7. Ruby — Check for `Gemfile` with RSpec or Minitest — run `bundle exec rspec` or `bundle exec rake test`.
8. C/C++ — Check for `CMakeLists.txt` with CTest, or a `Makefile` with test targets.

If none of these detect a known testing framework, ask the user: "I couldn't automatically detect the testing tool for this project. What command should I run to execute all tests?"

Run all tests using the detected command. Report which tests passed and which failed. For any failures, analyze the error output and suggest fixes.
