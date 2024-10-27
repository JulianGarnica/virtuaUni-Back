CREATE DATABASE VirtuaUni;
USE VirtuaUni;

-- Tabla para guardar tipos de mensajeros
CREATE TABLE TipoMensajero (
    idTipo INT PRIMARY KEY AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL
);


-- Tabla para gestionar los chats
CREATE TABLE Chats (
    idChat INT PRIMARY KEY AUTO_INCREMENT,
    nombreEstudiante TEXT,
    correoEstudiante TEXT,
    fechaCreacion DATETIME NOT NULL
);

-- Tabla para almacenar mensajes en un chat
CREATE TABLE Mensajes (
    idMensaje INT PRIMARY KEY AUTO_INCREMENT,
    idChat INT,
    idTipoMensajero INT,
    mensaje TEXT NOT NULL,
    fecha DATETIME NOT NULL,
    FOREIGN KEY (idTipoMensajero) REFERENCES TipoMensajero(idTipo),
    FOREIGN KEY (idChat) REFERENCES Chats(idChat)
);

-- Tabla para guardar las calificaciones dadas a un mensajero
CREATE TABLE Calificaciones (
    idCalificacion INT PRIMARY KEY AUTO_INCREMENT,
    idChat INT,
    calificacion INT NOT NULL CHECK (calificacion BETWEEN 1 AND 5),
    mensaje TEXT,
    fecha DATETIME NOT NULL,
    FOREIGN KEY (idChat) REFERENCES Chats(idChat)
);


INSERT INTO `TipoMensajero` (`idTipo`, `nombre`) VALUES
(1, 'user'),
(2, 'assistant');