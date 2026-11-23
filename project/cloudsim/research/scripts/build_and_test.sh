#!/usr/bin/env bash
# Build the research code against the official CloudSim 3.0.3 jar and run the scenario tests.
# Compiles with JDK 24 javac using --release 8 (Java 8 API + class files) and RUNS on the Java 8 JRE.
# No system-wide Java setting is changed: both tools are called by absolute path.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"                       # .../project/cloudsim/research
JAVAC="/c/Program Files/Java/jdk-24/bin/javac.exe"
JAVA8="/c/Program Files/Java/jre1.8.0_501/bin/java.exe"
CLOUDSIM_JAR="$(cygpath -m "$ROOT/../vendor/cloudsim-3.0.3/jars/cloudsim-3.0.3.jar")"
OUT="$ROOT/build/classes"

rm -rf "$OUT" && mkdir -p "$OUT"
find "$ROOT/src" "$ROOT/test" -name '*.java' | xargs -n1 cygpath -m > "$ROOT/build/sources.txt"
echo "javac: $("$JAVAC" -version 2>&1) --release 8"
"$JAVAC" --release 8 -Xlint:all -Xlint:-options -encoding UTF-8 \
    -cp "$CLOUDSIM_JAR" -d "$OUT" @"$(cygpath -m "$ROOT/build/sources.txt")"

echo "java:  $("$JAVA8" -version 2>&1 | head -1)"
CP="$CLOUDSIM_JAR;$(cygpath -m "$OUT")"
"$JAVA8" -cp "$CP" ckpt.app.MinimalDatacenter
"$JAVA8" -cp "$CP" ckpt.ScenarioTests
