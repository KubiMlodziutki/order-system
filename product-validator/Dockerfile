FROM maven:3.9-eclipse-temurin-17 AS build

WORKDIR /app

COPY pom.xml .
RUN mvn dependency:go-offline

COPY src ./src

# build
RUN mvn clean package -DskipTests

FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# co[y built jar]
COPY --from=build /app/target/product-validator-1.0-SNAPSHOT.jar app.jar

EXPOSE 8080

CMD ["java", \
     "--add-opens", "java.base/java.lang=ALL-UNNAMED", \
     "--add-opens", "java.base/java.io=ALL-UNNAMED", \
     "--add-opens", "java.base/java.util=ALL-UNNAMED", \
     "--add-opens", "java.base/java.lang.reflect=ALL-UNNAMED", \
     "--add-opens", "java.base/java.text=ALL-UNNAMED", \
     "--add-opens", "java.base/java.net=ALL-UNNAMED", \
     "-jar", "app.jar"]